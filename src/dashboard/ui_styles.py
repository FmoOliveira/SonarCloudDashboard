import streamlit as st
import os

def load_css(file_name: str) -> None:
    """Reads a CSS file and injects it securely into the Streamlit DOM."""
    # Ensure file_name contains no directory traversal characters
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        st.error("Security Error: Invalid CSS file path.", icon="🚨")
        return

    # Strictly read from the local directory of this module
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, file_name)
    
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            # Basic sanitization to prevent breaking out of the style block
            css_content = css_content.replace("</style>", "")
            
            # Use st.html in newer Streamlit, fallback to st.markdown
            if hasattr(st, "html"):
                st.html(f"<style>{css_content}</style>")
            else:
                st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS styling file could not be securely loaded.", icon="⚠️")

def inject_custom_css():
    """Injects custom CSS for modern UI elements"""
    load_css("custom.css")

def apply_theme_overrides(cookies=None) -> None:
    # Check if a theme is set in the cookies before falling back to session state
    if cookies and "theme_mode" in cookies and "theme_toggle_initialized" not in st.session_state:
        st.session_state.theme_toggle = (cookies["theme_mode"] == "light")
        st.session_state.theme_toggle_initialized = True

    if not st.session_state.get("theme_toggle", False):
        return
    
    load_css("light_theme.css")

def _theme_toggle_callback(cookies) -> None:
    # Save the current state of theme_toggle into cookies
    cookies["theme_mode"] = "light" if st.session_state.theme_toggle else "dark"
    # We must save immediately, importing the single_save function prevents element key clashes
    try:
        from auth_manager import _single_save
        _single_save(cookies)
    except ImportError:
        cookies.save()

def render_theme_toggle(cookies) -> None:
    """Renders the Light/Dark mode toggle switch in a responsive container and syncs to cookies."""
    if "theme_mode" in cookies and "theme_toggle_initialized" not in st.session_state:
        st.session_state.theme_toggle = (cookies["theme_mode"] == "light")
        st.session_state.theme_toggle_initialized = True

    # We use a container to align the toggle neatly without brittle column hardcoding
    with st.container():
        st.toggle("Light mode", key="theme_toggle", help="Toggle application light/dark theme", on_change=_theme_toggle_callback, args=(cookies,))
