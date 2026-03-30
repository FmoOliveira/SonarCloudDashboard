import streamlit as st
import os

def load_css(file_name: str) -> None:
    """Reads a CSS file and injects it into the Streamlit DOM."""
    # Ensure file_name contains no directory traversal characters
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        st.error("Security Error: Invalid CSS file path.", icon="🚨")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, file_name)
    
    if os.path.exists(full_path):
        with open(full_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    elif os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Use a generic warning to prevent path disclosure
        st.warning("CSS file not found.", icon="⚠️")

def inject_custom_css():
    """Injects custom CSS for modern UI elements"""
    load_css("custom.css")

def apply_theme_overrides() -> None:
    if not st.session_state.get("theme_toggle", False):
        return
    
    load_css("light_theme.css")

def render_theme_toggle() -> None:
    # Center the toggle using columns
    _, col, _ = st.columns([1, 3, 1])
    with col:
        st.toggle("Light mode", key="theme_toggle")
