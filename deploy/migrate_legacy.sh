#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly RELEASE_BRANCH="${1:-v2}"
readonly LEGACY_APP_ROOT="/opt/warlords-bot"
readonly LEGACY_ENV="${LEGACY_APP_ROOT}/src/.env"
readonly LEGACY_DATA="${LEGACY_APP_ROOT}/data"
readonly PANEL_ENV="/etc/warlords-bot-panel.env"
readonly APP_ROOT="/opt/warlords-bot-runtime"
readonly TARGET_DATA="/var/lib/warlords-bot/data"
readonly TARGET_ENV="/etc/warlords-bot.env"
readonly BOT_SERVICE="warlords-bot.service"
readonly PANEL_SERVICE="warlords-bot-panel.service"
readonly BOT_USER="warlords-bot"
readonly BOT_GROUP="warlords-bot"
readonly BACKUP_ROOT="/var/backups/warlords-bot-migration"
readonly BACKUP_DIR="${BACKUP_ROOT}/$(date -u +%Y%m%d-%H%M%S)"

unit_replaced=false
migration_complete=false
legacy_dropins_moved=false

rollback() {
    status=$?
    if (( status == 0 )) || [[ "${migration_complete}" == "true" ]]; then
        return
    fi

    echo "Migration failed; restoring the legacy bot service." >&2
    if [[ "${unit_replaced}" == "true" ]]; then
        install \
            -o root \
            -g root \
            -m 0644 \
            "${BACKUP_DIR}/warlords-bot.service.legacy" \
            "/etc/systemd/system/${BOT_SERVICE}"
        if [[ "${legacy_dropins_moved}" == "true" ]]; then
            mv \
                "${BACKUP_DIR}/warlords-bot.service.d.legacy" \
                "/etc/systemd/system/warlords-bot.service.d"
        fi
        systemctl daemon-reload
        systemctl restart "${BOT_SERVICE}" || true
    fi
    echo "Rollback files: ${BACKUP_DIR}" >&2
}
trap rollback EXIT

if (( EUID != 0 )); then
    echo "Legacy migration must run as root." >&2
    exit 2
fi
if [[ ! "${RELEASE_BRANCH}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
    echo "Invalid release branch: ${RELEASE_BRANCH}" >&2
    exit 3
fi
for required_file in \
    "${SCRIPT_DIR}/deploy.sh" \
    "${SCRIPT_DIR}/migrate_legacy_state.py" \
    "${SCRIPT_DIR}/warlords-bot.service" \
    "${SCRIPT_DIR}/warlords-bot-deploy.service" \
    "${SCRIPT_DIR}/warlords-bot-deploy.path"; do
    if [[ ! -f "${required_file}" ]]; then
        echo "Missing migration file: ${required_file}" >&2
        exit 4
    fi
done
if [[ ! -f "${LEGACY_ENV}" ]] || [[ ! -d "${LEGACY_DATA}" ]]; then
    echo "Legacy bot installation was not found." >&2
    exit 5
fi
if ! systemctl is-active --quiet "${BOT_SERVICE}"; then
    echo "Legacy bot service must be active before migration." >&2
    exit 6
fi

install -d -o root -g root -m 0700 "${BACKUP_DIR}"
install \
    -o root \
    -g root \
    -m 0644 \
    "/etc/systemd/system/${BOT_SERVICE}" \
    "${BACKUP_DIR}/warlords-bot.service.legacy"
if [[ -d "/etc/systemd/system/warlords-bot.service.d" ]]; then
    cp \
        -a \
        "/etc/systemd/system/warlords-bot.service.d" \
        "${BACKUP_DIR}/warlords-bot.service.d.legacy"
fi
if [[ -f "/etc/systemd/system/${PANEL_SERVICE}" ]]; then
    cp \
        -a \
        "/etc/systemd/system/${PANEL_SERVICE}" \
        "${BACKUP_DIR}/warlords-bot-panel.service.legacy"
fi
if [[ -d "/etc/systemd/system/warlords-bot-panel.service.d" ]]; then
    cp \
        -a \
        "/etc/systemd/system/warlords-bot-panel.service.d" \
        "${BACKUP_DIR}/warlords-bot-panel.service.d.legacy"
fi
if [[ -f "${PANEL_ENV}" ]]; then
    install -o root -g root -m 0600 "${PANEL_ENV}" "${BACKUP_DIR}/warlords-bot-panel.env.legacy"
fi
install -o root -g root -m 0600 "${LEGACY_ENV}" "${BACKUP_DIR}/warlords-bot.env.legacy"

if ! id "${BOT_USER}" >/dev/null 2>&1; then
    if ! getent group "${BOT_GROUP}" >/dev/null 2>&1; then
        groupadd --system "${BOT_GROUP}"
    fi
    useradd \
        --system \
        --gid "${BOT_GROUP}" \
        --home-dir "/var/lib/warlords-bot" \
        --shell /usr/sbin/nologin \
        "${BOT_USER}"
fi
install -d -o root -g root -m 0755 "${APP_ROOT}"
install -d -o "${BOT_USER}" -g "${BOT_GROUP}" -m 0750 "/var/lib/warlords-bot" "${TARGET_DATA}"

python3 "${SCRIPT_DIR}/migrate_legacy_state.py" \
    --legacy-env "${LEGACY_ENV}" \
    --panel-env "${PANEL_ENV}" \
    --legacy-data "${LEGACY_DATA}" \
    --backup-data "${BACKUP_DIR}/data" \
    --target-data "${TARGET_DATA}" \
    --target-env "${TARGET_ENV}"
chown -R "${BOT_USER}:${BOT_GROUP}" "/var/lib/warlords-bot"
chmod 0750 "/var/lib/warlords-bot" "${TARGET_DATA}"
find "${TARGET_DATA}" -maxdepth 1 -type f -name '*.sqlite3' -exec chmod 0640 {} +
chown root:root "${TARGET_ENV}"
chmod 0600 "${TARGET_ENV}"

cat >"/etc/warlords-bot-deploy.env" <<EOF
WARLORDS_BOT_RELEASE_BRANCH=${RELEASE_BRANCH}
WARLORDS_BOT_REPOSITORY_URL=https://github.com/TigranG8403/Warlords-multipurpose-bot.git
EOF
chown root:root "/etc/warlords-bot-deploy.env"
chmod 0600 "/etc/warlords-bot-deploy.env"

install -o root -g root -m 0755 "${SCRIPT_DIR}/deploy.sh" "/usr/local/sbin/warlords-bot-deploy"
install -o root -g root -m 0644 "${SCRIPT_DIR}/warlords-bot.service" "/etc/systemd/system/${BOT_SERVICE}"
install -o root -g root -m 0644 "${SCRIPT_DIR}/warlords-bot-deploy.service" "/etc/systemd/system/warlords-bot-deploy.service"
install -o root -g root -m 0644 "${SCRIPT_DIR}/warlords-bot-deploy.path" "/etc/systemd/system/warlords-bot-deploy.path"
unit_replaced=true

if [[ -d "/etc/systemd/system/warlords-bot.service.d" ]]; then
    mv \
        "/etc/systemd/system/warlords-bot.service.d" \
        "${BACKUP_DIR}/warlords-bot.service.d.active"
    legacy_dropins_moved=true
fi

systemctl daemon-reload
systemctl start "warlords-bot-deploy.service"
systemctl is-active --quiet "${BOT_SERVICE}"
systemctl enable "${BOT_SERVICE}"
systemctl enable --now "warlords-bot-deploy.path"

if systemctl list-unit-files "${PANEL_SERVICE}" --no-legend 2>/dev/null | grep -q "${PANEL_SERVICE}"; then
    systemctl disable --now "${PANEL_SERVICE}" || true
fi
install -d -o root -g root -m 0700 "${BACKUP_DIR}/retired-panel"
if [[ -f "/etc/systemd/system/${PANEL_SERVICE}" ]]; then
    mv "/etc/systemd/system/${PANEL_SERVICE}" "${BACKUP_DIR}/retired-panel/"
fi
if [[ -d "/etc/systemd/system/warlords-bot-panel.service.d" ]]; then
    mv "/etc/systemd/system/warlords-bot-panel.service.d" "${BACKUP_DIR}/retired-panel/"
fi
if [[ -f "${PANEL_ENV}" ]]; then
    mv "${PANEL_ENV}" "${BACKUP_DIR}/retired-panel/"
fi
systemctl daemon-reload
systemctl reset-failed "${PANEL_SERVICE}" 2>/dev/null || true

migration_complete=true
echo "Warlords Bot migration completed."
echo "Rollback files: ${BACKUP_DIR}"
