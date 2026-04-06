import html as _html


def get_login_card_html() -> str:
    return """
        <div style="
            background-color: var(--card-bg, #181B22);
            border: 1px solid var(--card-border, rgba(255, 255, 255, 0.1));
            border-radius: 16px;
            padding: 3rem;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        ">
            <div style="margin-bottom: 2rem;">
                <i class="iconoir-fingerprint" style="font-size: 5rem; color: #3B82F6; filter: drop-shadow(0 0 15px rgba(59, 130, 246, 0.4));"></i>
            </div>
            <h2 style="margin-bottom: 1rem; font-weight: 700;">Access Restricted</h2>
            <p style="color: var(--text-muted, #888); margin-bottom: 2.5rem; font-size: 1.1rem;">
                Authentication is required to access the enterprise SonarCloud metrics dashboard. 
                Please sign in with your corporate Entra ID account.
            </p>
        </div>
    """


def get_heading_html(
    title: str,
    icon_class: str,
    is_main_title: bool = False,
    has_bottom_padding: bool = False,
    top_margin: bool = False,
) -> str:
    """
    Generates a heading HTML element.
    
    Args:
        title: The heading text (will be HTML-escaped internally).
        icon_class: The Iconoir CSS class for the icon.
        is_main_title: If True, renders an <h1>; otherwise <h2>.
        has_bottom_padding: Adds bottom padding when True.
        top_margin: Adds top margin when True (replaces the previous "Controls" content check).
    """
    safe_title = _html.escape(title)
    safe_icon = _html.escape(icon_class)
    tag = "h1" if is_main_title else "h2"

    styles = "display: flex; align-items: center; gap: 0.5rem;"
    if is_main_title:
        styles += " margin: 0;"
    if has_bottom_padding:
        styles += " padding-bottom: 2rem;"
    if top_margin:
        styles += " margin-top: 1rem;"

    return f'<{tag} style="{styles}"><i class="{safe_icon}"></i> {safe_title}</{tag}>'


def get_profile_photo_html(photo_b64: str) -> str:
    """Renders the user's profile photo. Escapes the src attribute defensively."""
    safe_src = _html.escape(photo_b64)
    return (
        f'<div style="text-align: center;">'
        f'<img src="{safe_src}" style="width: 64px; height: 64px; border-radius: 50%;">'
        f'</div>'
    )


def get_profile_initials_html(initials: str) -> str:
    """Renders a profile avatar with initials. Escapes the initials content defensively."""
    safe_initials = _html.escape(initials)
    return (
        f'<div style="text-align: center;">'
        f'<div style="width: 64px; height: 64px; margin: 0 auto; border-radius: 50%; '
        f'background: #1db954; color: white; display: flex; justify-content: center; '
        f'align-items: center; font-weight: 700;">{safe_initials}</div>'
        f'</div>'
    )


def get_profile_name_html(user_name: str) -> str:
    """Renders the user's display name. Escapes the value defensively."""
    safe_name = _html.escape(user_name)
    return f"<p style='text-align: center; margin-top: 10px; margin-bottom: 10px;'><strong>{safe_name}</strong></p>"


def get_metric_card_html(
    safe_title: str,
    safe_value: str,
    safe_icon: str,
    safe_neon_class: str,
    safe_delta: str | None = None,
    safe_color: str | None = None,
) -> str:
    """
    Generates the metric card HTML. All string inputs are escaped internally
    for defence-in-depth even when callers have already escaped them.
    """
    title = _html.escape(safe_title)
    value = _html.escape(safe_value)
    icon = _html.escape(safe_icon)
    neon_class = _html.escape(safe_neon_class)

    delta_html = ""
    if safe_delta and safe_color:
        delta = _html.escape(safe_delta)
        color = _html.escape(safe_color)
        delta_html = f'''
<div class="neon-delta" style="color: {color};">
    {delta} <span class="neon-delta-label">vs start</span>
</div>'''

    return f'''
<div class="neon-card {neon_class}">
    <div class="neon-icon-container">
        <i class="{icon}"></i>
    </div>
    <div class="neon-title">
        {title}
    </div>
    <div class="neon-value">
        {value}
    </div>
    {delta_html}
</div>
'''
