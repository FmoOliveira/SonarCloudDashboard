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

def get_heading_html(title: str, icon_class: str, is_main_title: bool = False, has_bottom_padding: bool = False) -> str:
    tag = "h1" if is_main_title else "h2"
    padding = " padding-bottom: 2rem;" if has_bottom_padding else ""
    margin = " margin: 0;" if is_main_title else ""
    # Add top margin for sidebar controls
    margin += " margin-top: 1rem;" if not is_main_title and not has_bottom_padding and title == "Controls" else ""
    return f'<{tag} style="display: flex; align-items: center; gap: 0.5rem;{margin}{padding}"><i class="{icon_class}"></i> {title}</{tag}>'

def get_profile_photo_html(photo_b64: str) -> str:
    return f'<div style="text-align: center;"><img src="{photo_b64}" style="width: 64px; height: 64px; border-radius: 50%;"></div>'

def get_profile_initials_html(initials: str) -> str:
    return f'<div style="text-align: center;"><div style="width: 64px; height: 64px; margin: 0 auto; border-radius: 50%; background: #1db954; color: white; display: flex; justify-content: center; align-items: center; font-weight: 700;">{initials}</div></div>'

def get_profile_name_html(user_name: str) -> str:
    return f"<p style='text-align: center; margin-top: 10px; margin-bottom: 10px;'><strong>{user_name}</strong></p>"

def get_metric_card_html(safe_title: str, safe_value: str, safe_icon: str, safe_neon_class: str, safe_delta: str = None, safe_color: str = None) -> str:
    delta_html = ""
    if safe_delta and safe_color:
        delta_html = f'''
<div class="neon-delta" style="color: {safe_color};">
    {safe_delta} <span class="neon-delta-label">vs start</span>
</div>'''

    return f'''
<div class="neon-card {safe_neon_class}">
    <div class="neon-icon-container">
        <i class="{safe_icon}"></i>
    </div>
    <div class="neon-title">
        {safe_title}
    </div>
    <div class="neon-value">
        {safe_value}
    </div>
    {delta_html}
</div>
'''
