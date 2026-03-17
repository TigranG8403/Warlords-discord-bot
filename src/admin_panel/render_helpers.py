from __future__ import annotations

import html

def build_branch_picker(current_branch: str, branches: tuple[str, ...]) -> str:
    current_value = current_branch if current_branch in branches else (branches[0] if branches else "")
    current_label = current_value or "Нет удалённых веток"
    disabled_attr = " disabled" if not branches else ""
    options: list[str] = []

    if not branches:
        options.append(
            '<button type="button" class="branch-picker__option is-selected" '
            'data-branch-option data-value="" data-label="Нет удалённых веток" '
            'aria-selected="true" disabled>Нет удалённых веток</button>'
        )
    else:
        for branch in branches:
            selected = branch == current_value
            selected_class = " is-selected" if selected else ""
            selected_attr = "true" if selected else "false"
            escaped_branch = html.escape(branch)
            options.append(
                f'<button type="button" class="branch-picker__option{selected_class}" '
                f'data-branch-option data-value="{escaped_branch}" data-label="{escaped_branch}" '
                f'aria-selected="{selected_attr}">{escaped_branch}</button>'
            )

    return (
        '          <div class="branch-picker" data-branch-picker>\n'
        '            <span class="branch-picker__label">Удалённая ветка</span>\n'
        f'            <input type="hidden" name="branch" value="{html.escape(current_value)}" data-branch-input>\n'
        f'            <button type="button" class="branch-picker__trigger" data-branch-trigger aria-expanded="false" aria-haspopup="listbox"{disabled_attr}>\n'
        f'              <span class="branch-picker__value" data-branch-value>{html.escape(current_label)}</span>\n'
        '              <span class="branch-picker__caret" aria-hidden="true"></span>\n'
        '            </button>\n'
        f'            <div class="branch-picker__menu" data-branch-menu role="listbox">{"".join(options)}</div>\n'
        '          </div>'
    )


def render_avatar(label: str, avatar_url: str | None) -> str:
    if avatar_url:
        return f'<img class="avatar" src="{html.escape(avatar_url)}" alt="{html.escape(label)} avatar">'
    initial = (label[:1] or "?").upper()
    return f'<span class="avatar-fallback" aria-hidden="true">{html.escape(initial)}</span>'
