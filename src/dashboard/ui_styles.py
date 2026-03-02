import streamlit as st
import os

def load_css(file_name: str) -> None:
    """Reads a CSS file and injects it into the Streamlit DOM."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, file_name)
    
    if os.path.exists(full_path):
        with open(full_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    elif os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS file not found: {file_name}")

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
        </style>
    """, unsafe_allow_html=True)

def apply_theme_overrides() -> None:
    if not st.session_state.get("theme_toggle", False):
        return
    
    st.markdown("""
        <style>
            :root {
                --card-bg: #E7E4DD;
                --card-border: #D5D0C5;
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
            
            /* Input Fields */
            div[data-testid="stTextInput"] input,
            div[data-testid="stNumberInput"] input,
            div[data-testid="stDateInput"] input,
            div[data-testid="stTextArea"] textarea {
                color: #1A1814 !important;
                background-color: #FFFFFF !important;
                border-color: #D5D0C5 !important;
            }
            
            /* MultiSelect components */
            div[data-baseweb="select"], div[data-baseweb="select"] > div {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
            }
            span[data-baseweb="tag"] {
                background-color: #E7E4DD !important;
                border: 1px solid #D5D0C5 !important;
            }
            
            /* Buttons */
            div[data-testid="stButton"] > button,
            div[data-testid="stDownloadButton"] > button,
            button[data-testid="stBaseButton-secondary"] {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
            }

            /* Dataframe inversion */
            div[data-testid="stDataFrame"] canvas {
                filter: invert(1) hue-rotate(180deg) brightness(1.1) !important;
            }
            
            /* Toggle */
            div[data-testid="stToggle"] div[role="switch"][aria-checked="true"] {
                background-color: #2563EB !important;
            }
        </style>
    """, unsafe_allow_html=True)

def render_theme_toggle() -> None:
    st.toggle("Light mode", key="theme_toggle")
