#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY_URL="${WARLORDS_BOT_REPOSITORY_URL:-https://github.com/TigranG8403/Warlords-multipurpose-bot.git}"
readonly RELEASE_BRANCH="${WARLORDS_BOT_RELEASE_BRANCH:-v2}"
readonly APP_ROOT="${WARLORDS_BOT_APP_ROOT:-/opt/warlords-bot-runtime}"
readonly RELEASES_DIR="${APP_ROOT}/releases"
readonly CURRENT_LINK="${APP_ROOT}/current"
readonly DATA_DIR="${WARLORDS_BOT_DATA_DIR:-/var/lib/warlords-bot/data}"
readonly REQUEST_FILE="/var/lib/warlords-bot/deploy.request"
readonly READY_FILE="/run/warlords-bot/ready"
readonly SERVICE_NAME="warlords-bot.service"
readonly BOT_USER="warlords-bot"
readonly BOT_GROUP="warlords-bot"
readonly KEEP_RELEASES=5

staging_dir=""

cleanup() {
    rm -f -- "${REQUEST_FILE}"
    if [[ -n "${staging_dir}" && -d "${staging_dir}" ]]; then
        rm -rf -- "${staging_dir}"
    fi
}
trap cleanup EXIT

if [[ ! "${RELEASE_BRANCH}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
    echo "Invalid release branch: ${RELEASE_BRANCH}" >&2
    exit 2
fi

install -d -o root -g root -m 0755 "${APP_ROOT}" "${RELEASES_DIR}"
install -d -o "${BOT_USER}" -g "${BOT_GROUP}" -m 0750 "$(dirname "${DATA_DIR}")" "${DATA_DIR}"

exec 9>"${APP_ROOT}/deploy.lock"
if ! flock -n 9; then
    echo "Another Warlords Bot deployment is already running." >&2
    exit 3
fi

staging_dir="$(mktemp -d "${RELEASES_DIR}/.staging.XXXXXX")"
git clone \
    --depth 1 \
    --single-branch \
    --branch "${RELEASE_BRANCH}" \
    "${REPOSITORY_URL}" \
    "${staging_dir}/source"

commit_sha="$(git -C "${staging_dir}/source" rev-parse --verify HEAD)"
if [[ ! "${commit_sha}" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Git returned an invalid commit SHA." >&2
    exit 4
fi

release_dir="${RELEASES_DIR}/${commit_sha}"
if [[ ! -d "${release_dir}" ]]; then
    ln -s "${DATA_DIR}" "${staging_dir}/source/data"
    python3 -m venv "${staging_dir}/venv"
    "${staging_dir}/venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
    "${staging_dir}/venv/bin/python" -m pip install --disable-pip-version-check -r "${staging_dir}/source/requirements.txt"
    (
        cd "${staging_dir}/source"
        "${staging_dir}/venv/bin/python" -m unittest discover -s tests -v
        "${staging_dir}/venv/bin/python" -m compileall -q src tests
    )
    mv -- "${staging_dir}" "${release_dir}"
    staging_dir=""
fi

previous_release="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
next_link="${APP_ROOT}/.current.next"
rm -f -- "${next_link}"
ln -s "${release_dir}" "${next_link}"
mv -Tf -- "${next_link}" "${CURRENT_LINK}"

if ! systemctl restart "${SERVICE_NAME}"; then
    if [[ -n "${previous_release}" && -d "${previous_release}" ]]; then
        ln -s "${previous_release}" "${next_link}"
        mv -Tf -- "${next_link}" "${CURRENT_LINK}"
        systemctl restart "${SERVICE_NAME}" || true
    fi
    echo "Bot restart failed; previous release restored." >&2
    exit 5
fi

ready=false
for _attempt in $(seq 1 60); do
    if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
        break
    fi
    if [[ -s "${READY_FILE}" ]]; then
        ready=true
        break
    fi
    sleep 1
done

if [[ "${ready}" != "true" ]]; then
    if [[ -n "${previous_release}" && -d "${previous_release}" ]]; then
        ln -s "${previous_release}" "${next_link}"
        mv -Tf -- "${next_link}" "${CURRENT_LINK}"
        systemctl restart "${SERVICE_NAME}" || true
    else
        systemctl stop "${SERVICE_NAME}" || true
    fi
    echo "Bot did not remain active; previous release restored." >&2
    exit 6
fi

current_release="$(readlink -f "${CURRENT_LINK}")"
release_count=0
while IFS= read -r candidate; do
    [[ -n "${candidate}" ]] || continue
    release_count=$((release_count + 1))
    if (( release_count <= KEEP_RELEASES )) || [[ "${candidate}" == "${current_release}" ]]; then
        continue
    fi
    candidate_name="$(basename "${candidate}")"
    if [[ "${candidate}" != "${RELEASES_DIR}/${candidate_name}" ]] \
        || [[ ! "${candidate_name}" =~ ^[0-9a-f]{40}$ ]]; then
        echo "Refusing to remove unexpected release path: ${candidate}" >&2
        exit 7
    fi
    rm -rf -- "${candidate}"
done < <(
    find "${RELEASES_DIR}" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -name '[0-9a-f]*' \
        -printf '%T@ %p\n' \
        | sort -rn \
        | cut -d' ' -f2-
)

echo "Warlords Bot deployed successfully: ${commit_sha}"
