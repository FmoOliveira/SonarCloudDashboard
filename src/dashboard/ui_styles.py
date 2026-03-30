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
    st.markdown("""
        <style>
            .metric-card {
                background-color: var(--card-bg, #1e1e1e);
                border: 1px solid var(--card-border, #333);
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                box-shadow: var(--card-shadow, 0 4px 6px rgba(0,0,0,0.3));
                transition: transform 0.3s ease;
            }
            .metric-card:hover {
                transform: translateY(-5px);
            }
            .metric-value {
                font-size: 2rem;
                font-weight: 700;
                margin: 10px 0;
            }
            .metric-label {
                font-size: 0.9rem;
                color: var(--text-muted, #aaa);
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .neon-green { color: #00ff88; text-shadow: 0 0 10px rgba(0,255,136,0.5); }
            .neon-orange { color: #ff9d00; text-shadow: 0 0 10px rgba(255,157,0,0.5); }
            .neon-blue { color: #00d4ff; text-shadow: 0 0 10px rgba(0,212,255,0.5); }
            .neon-teal { color: #00f2ff; text-shadow: 0 0 10px rgba(0,242,255,0.5); }

            /* UNIFY ONLY SIDEBAR BUTTONS (Dark & Light Mode) */
            /* Exclude ALL header buttons (collapse, etc) from the blue style */
            section[data-testid="stSidebar"] button[data-testid^="stBaseButton-"]:not([kind*="header"]) {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
                border: 1px solid #2563EB !important;
                border-radius: 8px !important;
                transition: all 0.2s ease-in-out !important;
            }

            /* Universal white color for text and icons inside SIDEBAR buttons (excluding headers) */
            section[data-testid="stSidebar"] button[data-testid^="stBaseButton-"]:not([kind*="header"]) * {
                color: #FFFFFF !important;
                fill: #FFFFFF !important;
                vertical-align: middle;
            }

            /* Consistent Hover State for SIDEBAR buttons */
            section[data-testid="stSidebar"] button[data-testid^="stBaseButton-"]:not([kind*="header"]):hover {
                background-color: #1D4ED8 !important; 
                border-color: #1D4ED8 !important;
                box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
            }

            /* Ensure Collapse Button is Always Visible & Transparent */
            section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
                display: flex !important;
                visibility: visible !important;
                opacity: 1 !important;
                z-index: 9999 !important;
            }

            section[data-testid="stSidebar"] button[kind*="header"] {
                background-color: transparent !important;
                border-color: transparent !important;
                opacity: 1 !important;
                visibility: visible !important;
            }
            
            section[data-testid="stSidebar"] button[kind*="header"] * {
                fill: currentColor !important;
            }
        </style>
    """, unsafe_allow_html=True)

def apply_theme_overrides() -> None:
    if not st.session_state.get("theme_toggle", False):
        return
    
    st.markdown("""
        <style>
            :root {
                --card-bg: #E7E4DD;
                --card-border: #E7E4DD; /* Match background for borderless look */
                --card-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                --text-main: #1A1814;
                --text-dim: #3A3834;
                --text-muted: #5A5854;
            }
            html, body, div[data-testid="stApp"] {
                background-color: #F4F3EF !important;
                color: #1A1814 !important;
            }
            div[data-testid="stAppViewContainer"] { background-color: #F4F3EF !important; }
            section.main { background-color: transparent !important; }
            section[data-testid="stSidebar"], div[data-testid="stSidebar"] {
                background-color: #E7E4DD !important;
            }
            [data-testid="stSidebarNav"] span, div[data-testid="stSidebar"] label {
                color: #5A5854 !important;
            }
            div.block-container { color: #1A1814 !important; }
            h1, h2, h3, h4, h5, h6, p, span, label, li, a {
                color: #1A1814 !important;
            }
            a { color: #2563EB !important; }
            
            /* Borderless Containers */
            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-color: transparent !important;
            }

            /* Input Fields */
            div[data-testid="stTextInput"] input,
            div[data-testid="stNumberInput"] input,
            div[data-testid="stDateInput"] input,
            div[data-testid="stTextArea"] textarea {
                color: #1A1814 !important;
                background-color: #FFFFFF !important;
                border-color: #FFFFFF !important; /* Match their own background */
            }
            
            /* MultiSelect & SelectBox components */
            div[data-baseweb="select"], div[data-baseweb="select"] > div {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
                border-color: #FFFFFF !important;
            }
            span[data-baseweb="tag"],
            span[data-baseweb="tag"] span,
            span[data-baseweb="tag"] p {
                background-color: #E7E4DD !important;
                border: 1px solid #E7E4DD !important; /* Match background */
                color: #1A1814 !important;
            }
            span[data-baseweb="tag"] svg {
                fill: #1A1814 !important;
            }
            
            /* Dropdown Menus (Rendered outside main DOM) */
            div[data-testid="stPopoverBody"],
            div[data-baseweb="popover"] > div {
                background-color: #FFFFFF !important;
                border: 1px solid #FFFFFF !important;
                color: #1A1814 !important;
                border-radius: 8px !important;
            }
            div[data-baseweb="popover"] ul,
            div[data-baseweb="popover"] li {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
            }
            div[data-baseweb="popover"] li:hover {
                background-color: #F4F3EF !important;
            }

            /* st.pills & Segmented Control */
            div[data-testid="stSegmentedControl"] button,
            button[kind="pills"],
            button[data-testid="stBaseButton-pills"] {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
                border: 1px solid #FFFFFF !important;
            }
            button[kind="pills"] p,
            button[data-testid="stBaseButton-pills"] p {
                color: #1A1814 !important;
            }
            div[data-testid="stSegmentedControl"] button[aria-selected="true"],
            button[kind="pills"][aria-selected="true"],
            button[data-testid="stBaseButton-pills"][aria-selected="true"],
            button[kind="pills"][aria-checked="true"],
            button[data-testid="stBaseButton-pills"][aria-checked="true"] {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
                border-color: #2563EB !important;
            }
            button[kind="pills"][aria-selected="true"] p,
            button[kind="pills"][aria-checked="true"] p,
            button[data-testid="stBaseButton-pills"][aria-selected="true"] p,
            button[data-testid="stBaseButton-pills"][aria-checked="true"] p {
                color: #FFFFFF !important;
            }

            /* Popover Button specifically */
            button[data-testid="stPopoverButton"] {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
                border: 1px solid #FFFFFF !important;
            }
            button[data-testid="stPopoverButton"] p,
            button[data-testid="stPopoverButton"] svg {
                color: #1A1814 !important;
                fill: #1A1814 !important;
            }

            /* Logout & Popover Buttons Fix (Force Blue Style + White Text) */
            div[data-testid="stPopoverBody"] button {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
                border: 1px solid #2563EB !important;
                border-radius: 8px !important;
            }

            /* UNIVERSAL WHITE TEXT/ICONS FOR ALL BLUE BUTTONS */
            section[data-testid="stSidebar"] button[data-testid^="stBaseButton-"]:not([kind*="header"]) *,
            div[data-testid="stPopoverBody"] button *,
            div[data-testid="stDownloadButton"] button * {
                color: #FFFFFF !important;
                fill: #FFFFFF !important;
            }

            /* Unify Download Button with Sidebar Buttons in Light Mode */
            div[data-testid="stDownloadButton"] button {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
                border: 1px solid #2563EB !important;
                border-radius: 8px !important;
                transition: all 0.2s ease-in-out !important;
            }
            div[data-testid="stDownloadButton"] button * {
                color: #FFFFFF !important;
                fill: #FFFFFF !important;
            }
            div[data-testid="stDownloadButton"] button:hover {
                background-color: #1D4ED8 !important;
                border-color: #1D4ED8 !important;
                box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
            }

            /* Toolbar & Header Fix */
            header[data-testid="stHeader"] {
                background-color: transparent !important;
            }
            div[data-testid="stToolbar"] {
                background-color: transparent !important;
            }
            
            /* Style collapse button to match expand button's muted look */
            section[data-testid="stSidebar"] button[kind="header"] {
                color: rgba(229, 231, 235, 0.6) !important;
                background-color: transparent !important;
                border-color: transparent !important;
            }
            section[data-testid="stSidebar"] button[kind="header"] * {
                color: rgba(229, 231, 235, 0.6) !important;
                fill: rgba(229, 231, 235, 0.6) !important;
            }

            /* Dataframe inversion */
            div[data-testid="stDataFrame"] canvas {
                filter: invert(1) hue-rotate(180deg) brightness(1.1) !important;
            }
            
            /* Toggle */
            div[data-testid="stToggle"] div[role="switch"] {
                background-color: #D5D0C5 !important;
            }
            div[data-testid="stToggle"] div[role="switch"][aria-checked="true"] {
                background-color: #2563EB !important;
            }
        </style>
    """, unsafe_allow_html=True)

def render_theme_toggle() -> None:
    # Center the toggle using columns
    _, col, _ = st.columns([1, 3, 1])
    with col:
        st.toggle("Light mode", key="theme_toggle")
