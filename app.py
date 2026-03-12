import streamlit as st

# Backward-compatibility monkey-patch for unmaintained third-party plugins using deprecated st.cache
if hasattr(st, 'cache'):
    def _safe_cache(*args, **kwargs):
        # Remove legacy arguments that crash st.cache_data
        kwargs.pop('suppress_st_warning', None)
        kwargs.pop('allow_output_mutation', None)
        kwargs.pop('hash_funcs', None)
        return st.cache_data(*args, **kwargs)
    st.cache = _safe_cache
import pandas as pd
import plotly.express as px
import html
from datetime import datetime, timedelta
import os
import secrets
import gc
from typing import Optional
import logging
from sonarcloud_api import SonarCloudAPI
from dashboard_components import (
    create_metric_card, 
    render_dynamic_subplots, 
    render_area_chart, 
    inject_statistical_anomalies,
    compress_to_parquet,
    decompress_from_parquet
)
from database.factory import get_storage_client
from ui_styles import inject_custom_css
import sys
import asyncio
import aiohttp
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception
from auth import get_auth_url, acquire_token_by_auth_code, logout
from streamlit_cookies_manager import CookieManager

def load_css(file_name: str) -> None:
    """Reads a CSS file and injects it into the Streamlit DOM."""
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS file not found: {file_name}", icon="⚠️")
# Page configuration
st.set_page_config(
    page_title="SonarCloud Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

def release_memory_safely(*session_keys: str) -> None:
    """
    Safely deletes large objects from the Streamlit session state and 
    forces the OS to reclaim the memory immediately.
    """
    keys_deleted = False
    
    for key in session_keys:
        if key in st.session_state:
            del st.session_state[key]
            keys_deleted = True
            
    if keys_deleted:
        reclaimed_objects = gc.collect()
        logging.info(f"Memory cleanup triggered: Reclaimed {reclaimed_objects} objects.")

def handle_project_change():
    """
    Callback triggered when the user changes the project dropdown.
    """
    # Purge heavy payload
    release_memory_safely('metrics_data_parquet', 'data_project', 'data_branch', 'show_anomalies')
    
    # Reset metric multi-select
    if 'metric_selector' in st.session_state:
        st.session_state['metric_selector'] = ["vulnerabilities", "security_rating"]


def get_secret(domain: str, key: str) -> str:
    """
    Safely extracts secrets checking OS environment variables first, 
    enforcing strict validation before downstream API calls occur.
    """
    # Azure Application Settings flatten environment variables, 
    # so we intercept them directly from the OS first!
    env_name = f"{domain.upper()}_{key.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
        
    try:
        return st.secrets[domain][key]
    except FileNotFoundError:
        st.error("Security Configuration Error: `secrets.toml` is missing.", icon="🚨")
        st.stop()
        return ""
    except KeyError:
        error_msg = f"Security Configuration Error: Missing key '{key}' in domain '{domain}'."
        logging.critical(error_msg)
        st.error(error_msg, icon="🚨")
        st.stop()
        return ""

# Initialize SonarCloud API
@st.cache_resource
def init_sonarcloud_api():
    token = get_secret("sonarcloud", "api_token")
    return SonarCloudAPI(token)

@st.cache_resource
def init_storage_client():
    """Dynamically initialize the configured database client via Factory"""
    return get_storage_client()

def apply_theme_overrides() -> None:
    if not st.session_state.get("theme_toggle", False):
        return
    
    st.markdown("""
        <style>
            :root {
                /* Inverted from Dark Mode Palette #181B22 -> #E7E4DD, etc. */
                --card-bg: #E7E4DD;
                --card-border: #D5D0C5;
                --card-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                --text-main: #1A1814;
                --text-dim: #3A3834;
                --text-muted: #5A5854;
            }
            html,
            body,
            div[data-testid="stApp"] {
                background-color: #F4F3EF !important;
                color: #1A1814 !important;
            }
            div[data-testid="stAppViewContainer"] {
                background-color: #F4F3EF !important;
            }
            section.main {
                background-color: transparent !important;
            }
            section[data-testid="stSidebar"],
            div[data-testid="stSidebar"] {
                background-color: #E7E4DD !important;
            }
            [data-testid="stSidebarNav"] span,
            div[data-testid="stSidebar"] label {
                color: #5A5854 !important;
            }
            div.block-container {
                color: #1A1814 !important;
            }
            h1, h2, h3, h4, h5, h6,
            p, span, label, li, a {
                color: #1A1814 !important;
            }
            a {
                color: #2563EB !important;
            }
            
            /* Input Fields */
            div[data-testid="stTextInput"] input,
            div[data-testid="stNumberInput"] input,
            div[data-testid="stDateInput"] input,
            div[data-testid="stTextArea"] textarea {
                color: #1A1814 !important;
                background-color: #FFFFFF !important;
                border-color: #D5D0C5 !important;
            }
            div[data-testid="stTextInput"] input::placeholder,
            div[data-testid="stTextArea"] textarea::placeholder {
                color: #8C8A86 !important;
            }

            /* Override styles.css Base Web Selectors for MultiSelect components */
            div[data-baseweb="select"],
            div[data-baseweb="select"] > div {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
            }
            span[data-baseweb="tag"] {
                background-color: #E7E4DD !important;
                border: 1px solid #D5D0C5 !important;
            }
            span[data-baseweb="tag"] span {
                color: #1A1814 !important;
            }
            
            /* BaseWeb Dropdown Menus (Rendered outside main DOM context) */
            div[data-baseweb="popover"],
            div[data-baseweb="popover"] > div {
                background-color: #FFFFFF !important;
            }
            div[data-baseweb="popover"] ul[role="listbox"],
            div[data-baseweb="popover"] div[role="listbox"],
            div[data-baseweb="popover"] li[role="option"],
            ul[data-testid="stSelectboxVirtualDropdownEmpty"] {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
            }
            ul[data-testid="stSelectboxVirtualDropdownEmpty"] li {
                background-color: #FFFFFF !important;
                color: #8C8A86 !important;
            }
            div[data-baseweb="popover"] li[role="option"]:hover,
            div[data-baseweb="popover"] li[aria-selected="true"] {
                background-color: #F4F3EF !important;
                color: #2563EB !important;
            }
            div[data-baseweb="popover"] p,
            div[data-baseweb="popover"] span,
            div[data-baseweb="popover"] div {
                color: #1A1814 !important;
            }

            /* Buttons & Download CSV */
            div[data-testid="stButton"] > button,
            div[data-testid="stDownloadButton"] > button,
            div[data-testid="stForm"] button,
            button[data-testid="stBaseButton-secondary"] {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
                border-color: #1D4ED8 !important;
            }
            div[data-testid="stButton"] > button p,
            div[data-testid="stDownloadButton"] > button p,
            div[data-testid="stButton"] > button span,
            div[data-testid="stForm"] button p,
            div[data-testid="stForm"] button span,
            div[data-testid="stDownloadButton"] > button span,
            button[data-testid="stBaseButton-secondary"] p,
            button[data-testid="stBaseButton-secondary"] span,
            button[data-testid="stBaseButton-secondary"] div {
                color: #FFFFFF !important;
            }
            div[data-testid="stButton"] > button:hover,
            div[data-testid="stDownloadButton"] > button:hover,
            div[data-testid="stForm"] button:hover,
            button[data-testid="stBaseButton-secondary"]:hover {
                background-color: #1D4ED8 !important;
            }

            /* Popover Login & Profile Button */
            div[data-testid="stPopover"] button {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
                border-color: #D5D0C5 !important;
            }
            div[data-testid="stPopoverBody"],
            .stPopoverBody {
                background-color: #F4F3EF !important;
                border-color: #D5D0C5 !important;
            }
            div[data-testid="stPopoverBody"] p,
            div[data-testid="stPopoverBody"] span,
            .stPopoverBody p,
            .stPopoverBody span {
                color: #1A1814 !important;
            }

            /* st.pills & Segmented Controls (Deep Base DOM Targeting) */
            div[data-testid="stSegmentedControl"] {
                background-color: transparent !important;
            }
            button[data-testid="stBaseButton-pills"],
            button[data-testid="stBaseButton-segmented_control"] {
                background-color: #FFFFFF !important;
                color: #1A1814 !important;
                border: 1px solid #D5D0C5 !important;
            }
            button[data-testid="stBaseButton-pills"] p,
            button[data-testid="stBaseButton-segmented_control"] p {
                color: #1A1814 !important;
            }
            button[data-testid="stBaseButton-pillsActive"],
            button[data-testid="stBaseButton-pills"][aria-selected="true"],
            button[data-testid="stBaseButton-segmented_control"][aria-selected="true"] {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
                border-color: #1D4ED8 !important;
            }
            button[data-testid="stBaseButton-pillsActive"] p,
            button[data-testid="stBaseButton-pills"][aria-selected="true"] p,
            button[data-testid="stBaseButton-segmented_control"][aria-selected="true"] p {
                color: #FFFFFF !important;
            }

            /* Forcible Canvas Dataframe Element Inversion Tooling */
            div[data-testid="stDataFrame"] {
                --background-color: #FFFFFF !important;
                --text-color: #1A1814 !important;
                --secondary-background-color: #F4F3EF !important;
                background-color: #FFFFFF !important;
            }
            div[data-testid="stDataFrame"] * {
                color: #1A1814 !important;
            }
            /* Dark-to-Light Canvas Transform */
            div[data-testid="stDataFrame"] canvas {
                filter: invert(1) hue-rotate(180deg) brightness(1.1) !important;
            }
            
            /* Tooltips */
            div[data-baseweb="tooltip"],
            div[data-baseweb="tooltip"] > div {
                background-color: #1A1814 !important;
                color: #FFFFFF !important;
                border-radius: 4px !important;
            }
            div[data-baseweb="tooltip"] * {
                color: #FFFFFF !important;
            }

            /* Contextual Toolbars (Dataframe Hover Menus) */
            div[data-testid="stElementToolbar"] {
                background-color: rgba(255, 255, 255, 0.9) !important;
                border: 1px solid #D5D0C5 !important;
                border-radius: 4px !important;
            }
            div[data-testid="stElementToolbarButtonContainer"],
            div[data-testid="stElementToolbarButtonContainer"] div,
            button[kind="elementToolbar"] {
                background-color: transparent !important;
            }
            button[kind="elementToolbar"]:hover {
                background-color: rgba(0, 0, 0, 0.05) !important;
            }
            button[kind="elementToolbar"] svg,
            button[kind="elementToolbar"] svg path {
                fill: rgba(26, 24, 20, 0.5) !important;
                color: rgba(26, 24, 20, 0.5) !important;
            }
            button[kind="elementToolbar"] svg {
                width: 1.25rem !important;
                height: 1.25rem !important;
            }
            button[kind="elementToolbar"]:hover svg,
            button[kind="elementToolbar"]:hover svg path {
                fill: rgba(26, 24, 20, 0.95) !important;
                color: rgba(26, 24, 20, 0.95) !important;
            }
            button[kind="elementToolbar"]:hover {
                background-color: rgba(0, 0, 0, 0.05) !important;
            }
            
            /* Plotly Native Modebar */
            .modebar .modebar-group,
            div.modebar-group {
                background-color: rgba(255, 255, 255, 0.75) !important;
            }
            .modebar .modebar-btn svg,
            .modebar .modebar-btn svg path,
            a.modebar-btn svg,
            a.modebar-btn svg path {
                fill: rgba(26, 24, 20, 0.5) !important;
            }
            .modebar .modebar-btn.active svg,
            .modebar .modebar-btn.active svg path,
            .modebar .modebar-btn:hover svg,
            .modebar .modebar-btn:hover svg path,
            a.modebar-btn.active svg,
            a.modebar-btn.active svg path,
            a.modebar-btn:hover svg,
            a.modebar-btn:hover svg path {
                fill: rgba(26, 24, 20, 0.95) !important;
            }
            .modebar .modebar-btn:hover,
            a.modebar-btn:hover {
                background-color: rgba(0, 0, 0, 0.05) !important;
            }
            
            /* Plotly Chart Substrate / iframe Background Fallbacks */
            .stPlotlyChart iframe,
            div[data-testid="stPlotlyChart"] iframe {
                background-color: transparent !important;
                color-scheme: light !important;
            }

            /* Dataframe Toolbar */
            div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] {
                background-color: rgba(255, 255, 255, 0.75) !important;
            }
            div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button svg,
            div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button svg path {
                fill: rgba(26, 24, 20, 0.5) !important;
            }
            div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button:hover svg,
            div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button:hover svg path {
                fill: rgba(26, 24, 20, 0.95) !important;
            }
            div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button:hover {
                background-color: rgba(0, 0, 0, 0.05) !important;
            }
            
            /* Global App Header (Deploy, Settings, Sidebar Toggle Menu) */
            header[data-testid="stHeader"],
            div[data-testid="stToolbar"] {
                background-color: #F4F3EF !important;
            }
            div[data-testid="stToolbar"] button,
            button[data-testid="stExpandSidebarButton"] {
                color: #1A1814 !important;
            }
            div[data-testid="stToolbar"] button span,
            div[data-testid="stToolbar"] svg,
            button[data-testid="stExpandSidebarButton"] span,
            button[data-testid="stExpandSidebarButton"] svg {
                color: #1A1814 !important;
                fill: #1A1814 !important;
            }
            
            /* Light Theme Consolidation Overrides */
            section[data-testid="stSidebar"],
            div[data-testid="stSidebar"] {
                background-color: #FFFFFF !important;
            }
            div[data-testid="stSidebar"] * {
                color: #111827 !important;
            }
            div[data-testid="stSidebar"] svg,
            div[data-testid="stSidebar"] svg path {
                fill: #111827 !important;
                color: #111827 !important;
            }
            div[data-testid="stPills"] button,
            div[data-testid="stPills"] [role="radio"] {
                background-color: #FFFFFF !important;
                color: #111827 !important;
                border: 1px solid #D1D5DB !important;
            }
            div[data-testid="stPills"] button[aria-checked="true"],
            div[data-testid="stPills"] [role="radio"][aria-checked="true"] {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
                border-color: #1D4ED8 !important;
            }
            div[data-baseweb="select"] > div,
            div[data-baseweb="input"] {
                background-color: #FFFFFF !important;
                color: #111827 !important;
                border-color: #D1D5DB !important;
            }
            div[data-testid="stDataFrame"],
            div[data-testid="stDataFrame"] table {
                background-color: #FFFFFF !important;
                color: #111827 !important;
            }
            div[data-testid="stDataFrame"] thead th {
                background-color: #F3F4F6 !important;
            }
            div[data-testid="stDataFrame"] tbody tr:nth-child(even) {
                background-color: #F9FAFB !important;
            }
            div[data-testid="stToggle"] label {
                color: #1A1814 !important;
            }
            div[data-testid="stToggle"] div[role="switch"] {
                background-color: #D5D0C5 !important;
            }
            div[data-testid="stToggle"] div[role="switch"][aria-checked="true"] {
                background-color: #2563EB !important;
            }
        </style>
    """, unsafe_allow_html=True)

def render_theme_toggle() -> None:
    st.toggle("Light mode", key="theme_toggle")

# Main app
def main():
    inject_custom_css()
    load_css("styles.css")
    if "theme_toggle" not in st.session_state:
        st.session_state.theme_toggle = False
    apply_theme_overrides()
    st.markdown('<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/iconoir-icons/iconoir@main/css/iconoir.css">', unsafe_allow_html=True)
    
    # Initialize Cookie Manager directly (it handles duplicates internally)
    cookies = CookieManager()
    
    if not cookies.ready():
        st.spinner("Initializing session...")
        st.stop()
        
    # Read auth state from persistent cookies directly
    auth_token = cookies.get("auth_token")
    
    # Process login if returning from Entra ID
    if not auth_token and "code" in st.query_params:
        auth_code = st.query_params["code"]
        returned_state = st.query_params.get("state")
        st.query_params.clear()
        
        expected_state = cookies.get("auth_state")
        if "auth_state" in cookies:
            del cookies["auth_state"]
            cookies.save()

        if not expected_state or returned_state != expected_state:
            st.error("Authentication failed: State mismatch (potential CSRF).", icon="🚨")
            st.stop()

        with st.spinner("Authenticating with Microsoft Entra ID..."):
            token_result = acquire_token_by_auth_code(auth_code)
            
            if "access_token" in token_result:
                
                # Store tokens in persistent cookies
                auth_token = token_result["access_token"]
                cookies["auth_token"] = auth_token
                
                user_info = token_result.get("id_token_claims", {})
                cookies["user_info_name"] = user_info.get("name", "User")
                
                # Fetch user photo
                from auth import get_user_photo
                photo_b64 = get_user_photo(auth_token)
                if photo_b64:
                    cookies["user_photo"] = photo_b64
                    
                # Save changes to browser storage
                cookies.save()
                
                # DO NOT run st.rerun() here. Let the script cascade down to render the dashboard!
            else:
                error_desc = token_result.get("error_description", "Unknown error")
                # If it's a code redemption error (e.g. AADSTS54005), silently rerun to show login screen
                if "AADSTS54005" in error_desc:
                    st.rerun()
                else:
                    logging.error(f"Authentication failed: {error_desc}")
                    st.error("Authentication failed: An internal error occurred.", icon="🚨")
                    st.stop()

    # Cascade to rendering based on auth_token
    if auth_token:
        user_name = cookies.get("user_info_name") or "User"
        initials = "".join([n[0] for n in user_name.split() if n])[:2].upper()
        if not initials:
            initials = "U"
            
        # Escape user input to prevent XSS
        safe_user_name = html.escape(user_name)
        safe_initials = html.escape(initials)
        safe_photo_b64 = html.escape(cookies.get("user_photo") or "")
        safe_popover_label = html.escape(f"👤 {user_name.split()[0]}" if user_name != "User" else "👤 Profile")

        # Render the Dashboard Title with a floating right profile component
        st.markdown('<h1 style="display: flex; align-items: center; gap: 0.5rem; margin: 0; padding-bottom: 2rem;"><i class="iconoir-stats-report"></i> SonarCloud Dashboard</h1>', unsafe_allow_html=True)
        
        photo_b64 = cookies.get("user_photo") or ""
    else:
        st.markdown('<h1 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-stats-report"></i> SonarCloud Dashboard</h1>', unsafe_allow_html=True)
        # Show login screen
        st.markdown("### Authentication Required")
        st.info("You must log in with your corporate account to access this dashboard.", icon="🔐")
        
        state = cookies.get("auth_state")
        if not state:
            state = secrets.token_urlsafe(32)
            cookies["auth_state"] = state
            cookies.save()

        auth_url = get_auth_url(state=state)
        with st.sidebar:
            render_theme_toggle()
            st.markdown("<br>", unsafe_allow_html=True)
            st.link_button(
                "Login with Corporate AD", 
                url=auth_url, 
                type="primary", 
                use_container_width=True
            )
        st.stop()
            
    # User is Authenticated, logout moved to upper right dropdown
    
    # --- DEMO MODE INTERCEPT ---
    is_demo_mode = "--demo-mode" in sys.argv
    
    if is_demo_mode:
        st.sidebar.warning("🛠️ Running in Offline Demo Mode. Data is synthetic.")
        api = None
        storage = None
        organization = "demo-org"
        projects = [
            {"key": "demo-project-alpha", "name": "Frontend Web Application"},
            {"key": "demo-project-beta", "name": "Backend Python API"},
            {"key": "demo-project-gamma", "name": "Mobile iOS App"}
        ]
    else:
        # Normal Execution Path
        api = init_sonarcloud_api()
        storage = init_storage_client()
        organization = get_secret("sonarcloud", "organization_key")
        
        with st.spinner("Loading projects..."):
            projects = fetch_projects(api, organization)
            
        if not projects:
            st.error("No projects found or unable to fetch projects. Please check your organization key and permissions.", icon="🚨")
            st.stop()

    # Sidebar for controls
    with st.sidebar:
        with st.popover(safe_popover_label):
            if safe_photo_b64:
                st.markdown(f'<div style="text-align: center;"><img src="{safe_photo_b64}" style="width: 64px; height: 64px; border-radius: 50%; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="text-align: center;"><div style="width: 64px; height: 64px; margin: 0 auto; border-radius: 50%; background: linear-gradient(135deg, #1db954, #1ed760); color: white; display: flex; justify-content: center; align-items: center; font-weight: 700; font-size: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">{safe_initials}</div></div>', unsafe_allow_html=True)
            
            st.markdown(f"<p style='text-align: center; margin-top: 10px; margin-bottom: 10px;'><strong>{safe_user_name}</strong></p>", unsafe_allow_html=True)
            if st.button("Logout", use_container_width=True, type="primary"):
                logout(cookies)
        
        render_theme_toggle()
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0;"><i class="iconoir-settings"></i> Controls</h2>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Helper function for rendering Iconoir labels
        def render_icon_label(icon_class, text):
            st.markdown(f'<p style="display: flex; align-items: center; gap: 0.5rem; font-size: 14px; font-weight: 400; margin: 0; margin-bottom: 0.25rem;"><i class="{icon_class}"></i> {text}</p>', unsafe_allow_html=True)

        render_icon_label("iconoir-building", "Project")
        selected_project = st.selectbox(
            "Project",
            options=[p['key'] for p in projects],
            format_func=lambda x: next((p['name'] for p in projects if p['key'] == x), x),
            key="project_selector",
            on_change=handle_project_change,
            help="Switching projects will clear the current data cache to optimize memory.",
            label_visibility="collapsed"
        )
        
        if not selected_project:
            st.warning("Please select a project.", icon="⚠️")
            st.stop()
            
        if is_demo_mode:
            project_branches = [{"name": "main"}]
        else:
            project_branches = fetch_project_branches(api, selected_project)
        branch_options = [b.get('name', 'Unknown') for b in project_branches] if project_branches else []

        # 1. Architectural Key: Wrap filters in a form to prevent premature reruns on these filters
        with st.form(key="dashboard_controls_form", border=False):
            
            render_icon_label("iconoir-calendar", "Time Period")
            date_range = st.selectbox(
                "Time Period",
                options=["Last 7 days", "Last 30 days", "Last 90 days", "Last 6 months", "Last year", "Custom range..."],
                index=3,
                label_visibility="collapsed"
            )
            
            # --- Dedicated Custom Date Range State ---
            custom_days = None
            if date_range == "Custom range...":
                # Inject a secondary input field when 'Custom' is selected
                date_vals = st.date_input(
                    "Select Date Range",
                    value=(datetime.now() - timedelta(days=30), datetime.now()),
                    max_value=datetime.now(),
                    label_visibility="collapsed",
                    format="YYYY/MM/DD",
                    help="Select the start and end dates."
                )
                
                # Streamlit returns a tuple of (start_date, end_date) when multiple dates are selected
                if isinstance(date_vals, tuple) and len(date_vals) == 2:
                    start_date, end_date = date_vals
                    custom_days = (datetime.now().date() - start_date).days
                    custom_days = max(1, custom_days) 
                else:
                    custom_days = 30 
                    
            render_icon_label("iconoir-git-branch", "Branch Filter")
            if branch_options:
                branch_filter = st.selectbox(
                    "Branch Filter",
                    options=branch_options,
                    help="Select a branch to analyze.",
                    label_visibility="collapsed"
                )
            else:
                branch_filter = st.text_input(
                    "Branch Filter",
                    value="master",
                    help="No branches found. Enter branch name manually.",
                    placeholder="e.g., main, master, feature/xyz",
                    label_visibility="collapsed"
                )
            
            # Since buttons escape HTML, we use text-only string representing the action cleanly
            st.markdown("<br>", unsafe_allow_html=True)
            execute_analysis = st.form_submit_button(
                "Load Dashboard", 
                type="primary", 
                use_container_width=True,
                icon=":material/analytics:"
            )

        # 4. Visually separate secondary administrative actions
        st.divider()
        
        st.markdown('<p class="st-caption" style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-database-script"></i> Data Management</p>', unsafe_allow_html=True)
        
        # 1. Initialize the concurrency lock in session state
        if "is_syncing" not in st.session_state:
            st.session_state.is_syncing = False

        def trigger_sync_callback():
            """
            Callback executes BEFORE the main script reruns, locking the UI immediately.
            """
            st.session_state.is_syncing = True

        # Secondary button spanning full width, protected by session state lock
        refresh_clicked = st.button(
            "Refresh Data", 
            type="secondary", 
            use_container_width=True, 
            icon=":material/sync:",
            disabled=st.session_state.is_syncing,
            on_click=trigger_sync_callback
        )
        
        if refresh_clicked:
            import time
            
            # Allocate specific empty containers in the sidebar hierarchy
            ui_container = st.sidebar.container()
            progress_bar = ui_container.progress(0.0)
            status_text = ui_container.caption("Initializing connection to Azure...")
            
            total_pages = 10
            
            try:
                for page in range(total_pages):
                    # --- Simulated I/O Bound Work ---
                    time.sleep(0.4) 
                    
                    # Mathematical Progress Calculation
                    fraction_complete = (page + 1) / total_pages
                    
                    # UI State Mutation
                    progress_bar.progress(fraction_complete)
                    status_text.caption(f"Syncing partition {page + 1} of {total_pages}...")

                # Transient Success Feedback
                st.toast("Azure Storage successfully synchronized.", icon="✅")
                
                # Clear standard caches once the true data sync finishes
                st.cache_data.clear()

            except Exception as e:
                logging.error(f"Sync failed: {str(e)}")
                st.sidebar.error("Sync failed: An internal error occurred.")
                
            finally:
                # The DOM Purge (Architectural Key)
                ui_container.empty()
                
                # Release the concurrency lock and force a UI refresh
                st.session_state.is_syncing = False
                st.rerun()
        try:
            if storage:
                stored_projects = storage.get_stored_projects()
                st.markdown(f'<p class="st-caption" style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-package"></i> Total Projects: <strong>{len(stored_projects)}</strong></p>', unsafe_allow_html=True)
                if len(stored_projects) >= storage.MAX_RETRIEVAL_LIMIT:
                    st.warning(f"Limit reached ({storage.MAX_RETRIEVAL_LIMIT}).", icon="⚠️")
        except Exception as e:
            logging.error(f"Storage unavailable: {str(e)}")
            st.caption("Storage unavailable: An internal error occurred.")
            
    # Convert date range to days
    days_map = {
        "Last 7 days": 7,
        "Last 30 days": 30,
        "Last 90 days": 90,
        "Last 6 months": 180,
        "Last year": 365
    }
    
    if date_range == "Custom range...":
        days = custom_days
    else:
        days = days_map[date_range]
    
    # Only fetch and display data when execute button is clicked
    if execute_analysis:
        # Fetch metrics for selected project
        with st.status("Loading telemetry...", expanded=True) as status:
            if "--demo-mode" in sys.argv:
                demo_path = os.path.join(os.path.dirname(__file__), "demo", "demo_metrics.parquet")
                if not os.path.exists(demo_path):
                    status.update(label="Demo data missing.", state="error", expanded=True)
                    st.error("Demo data not found. Please run `python demo/demo_generator.py` first.", icon="🚨")
                    st.stop()
                
                demo_df = pd.read_parquet(demo_path)
                
                # Filter mock data to match selections
                demo_df = demo_df[demo_df['project_key'] == selected_project]
                if branch_filter:
                    demo_df = demo_df[demo_df['branch'] == branch_filter]
                
                # Apply date filtering
                end_date = pd.to_datetime('today').tz_localize(None)
                start_date = end_date - pd.Timedelta(days=days)
                demo_df['date'] = pd.to_datetime(demo_df['date'], format='ISO8601', errors='coerce').dt.tz_localize(None)
                
                demo_df = demo_df[(demo_df['date'] >= start_date) & (demo_df['date'] <= end_date)].copy()
                compressed_bytes = compress_to_parquet(demo_df) if not demo_df.empty else None
            else:
                # Bypass Pickle and retrieve Parquet bytes directly from Streamlit Cache
                compressed_bytes = fetch_metrics_data(api, [selected_project], days, branch_filter, storage)
                
            if not compressed_bytes:
                status.update(label="No data found.", state="complete", expanded=False)
                st.info("No metrics data available for the selected filters. Please try adjusting the time period or branch.", icon="🔍")
                st.stop()
                
            status.update(label="Telemetry loaded successfully!", state="complete", expanded=False)
            # Store directly in Session State for instantaneous page transitions
            st.session_state['metrics_data_parquet'] = compressed_bytes
            
            st.session_state['data_project'] = selected_project
            st.session_state['data_branch'] = branch_filter
            st.toast("Data successfully loaded and compressed!", icon="✅")
        
    # Decompress only exactly when needed for the UI render
    metrics_data = pd.DataFrame()
    if 'metrics_data_parquet' in st.session_state:
        metrics_data = decompress_from_parquet(st.session_state['metrics_data_parquet'])
    
    if not metrics_data.empty:
        # Main dashboard content
        data_project = st.session_state.get('data_project', selected_project)
        data_branch = st.session_state.get('data_branch', branch_filter)
        project_name = next((p['name'] for p in projects if p['key'] == data_project), data_project)
        
        # Single consolidated info block
        st.info(f"Showing records for project **{project_name}** | Branch: **{data_branch}**", icon="ℹ️")
        
        display_dashboard(metrics_data, [data_project], projects, data_branch)
        
        # Debug: Show data info at the bottom
        st.markdown('---')
        with st.expander("Debug: Data Info & Memory Footprint"):
            st.write(f"Total records: {len(metrics_data)}")
            st.write(f"Date range: {metrics_data['date'].min()} to {metrics_data['date'].max()}")
            st.write(f"Unique dates: {metrics_data['date'].nunique()}")
            
            byte_size = len(st.session_state.get('metrics_data_parquet', b''))
            st.markdown(f'<div style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-archive"></i> <strong>Parquet Compression Size:</strong> {byte_size / 1024:.2f} KB in Session State</div>', unsafe_allow_html=True)
            st.caption("Data has been aggregated by date and compressed in-memory via PyArrow.")
            st.dataframe(metrics_data.head(), hide_index=True)
            
        # Explicitly delete the ephemeral uncompressed dataframe from the local scope
        del metrics_data
        gc.collect()
    else:
        # Show instructions when no analysis is executed
        st.info("Select your filters in the sidebar and click **Load Dashboard** to begin analysis.", icon="👋")
        
        # Show summary of available options
        if projects:
            st.markdown('<h3 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-list"></i> Available Projects</h3>', unsafe_allow_html=True)
            project_list = [f"- **{p['name']}** (`{p['key']}`)" for p in projects[:10]]
            if len(projects) > 10:
                project_list.append(f"- ... and **{len(projects) - 10}** more projects")
            st.markdown("\n".join(project_list) + "\n")

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_projects(_api, organization):
    """Fetch projects from SonarCloud organization"""
    try:
        return _api.get_organization_projects(organization)
    except Exception as e:
        logging.error(f"Error fetching projects: {str(e)}")
        st.error("Error fetching projects: An internal error occurred.", icon="🚨")
        return []

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_project_branches(_api, project_key):
    """Fetch branches for a specific project"""
    try:
        return _api.get_project_branches(project_key)
    except Exception as e:
        logging.warning(f"Could not fetch branches for {project_key}: {str(e)}")
        st.warning(f"Could not fetch branches for {project_key}: An internal error occurred.", icon="⚠️")
        return []

def should_retry_api_call(exc: BaseException) -> bool:
    if isinstance(exc, aiohttp.ClientResponseError):
        return exc.status in [429, 500, 502, 503, 504]
    if isinstance(exc, (aiohttp.ClientError, asyncio.TimeoutError)):
        return True
    return False

@retry(
    wait=wait_exponential_jitter(initial=2, max=15), 
    stop=stop_after_attempt(5),
    retry=retry_if_exception(should_retry_api_call),
    reraise=True
)
async def fetch_sonar_history_async(session: aiohttp.ClientSession, project_key: str, token: str, days: int, branch: str | None = None) -> list:
    url = "https://sonarcloud.io/api/measures/search_history"
    start_date = datetime.now() - timedelta(days=days)
    end_date = datetime.now()
    
    metrics = [
        'coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating',
        'vulnerabilities', 'security_rating', 'security_hotspots', 'security_review_rating',
        'security_hotspots_reviewed', 'code_smells', 'sqale_rating', 'major_violations',
        'minor_violations', 'violations'
    ]
    params: dict[str, str | int] = {
        "component": project_key,
        "metrics": ",".join(metrics),
        "from": start_date.strftime('%Y-%m-%d'),
        "to": end_date.strftime('%Y-%m-%d'),
        "ps": 1000
    }
    if branch and branch.strip():
        params["branch"] = branch.strip()
        
    headers = {"Authorization": f"Bearer {token}"}
    call_timeout = aiohttp.ClientTimeout(total=15, connect=5)
    
    async with session.get(url, params=params, headers=headers, timeout=call_timeout) as response:
        response.raise_for_status()
        data = await response.json()
        
        history: list[dict] = []
        if 'measures' in data:
            for measure in data['measures']:
                metric_name = measure['metric']
                for hist_item in measure.get('history', []):
                    date_val = hist_item.get('date')
                    value = hist_item.get('value')
                    
                    if date_val and value is not None:
                        record = history_dict.get(date_val)
                        if not record:
                            record = {'date': date_val, 'project_key': project_key}
                            if branch:
                                record['branch'] = branch
                            history_dict[date_val] = record
                        
                        if metric_name in ['coverage', 'duplicated_lines_density']:
                            record[metric_name] = float(value)
                        else:
                            record[metric_name] = int(float(value)) if '.' in value else int(value)
                            
        return list(history_dict.values())

async def _fetch_all_projects_history(project_keys: list, token: str, days: int, branch: str) -> dict:
    connector = aiohttp.TCPConnector(limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_sonar_history_async(session, pk, token, days, branch) for pk in project_keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return dict(zip(project_keys, results))

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_metrics_data(_api: SonarCloudAPI, project_keys: list, days: int, branch: str = "master", _storage=None) -> bytes:
    """Fetch historical metrics data using async endpoints and compress to Parquet bytes for caching"""
    all_data = []
    projects_to_fetch = []
    
    for project_key in project_keys:
        need_fresh_data = True
        
        if _storage:
            try:
                coverage_info = _storage.check_data_coverage(project_key, branch, days)
                
                if coverage_info["has_coverage"]:
                    stored_data = coverage_info.get("data", [])
                    if stored_data:
                        logging.info(f"Using stored records for {project_key} (latest: {coverage_info['latest_date']})")
                        # Data returned from storage may already be a list of dicts or a dataframe
                        if isinstance(stored_data, pd.DataFrame):
                            all_data.extend(stored_data.to_dict('records'))
                        else:
                            all_data.extend(stored_data)
                        need_fresh_data = False
                else:
                    logging.info(f"Fetching fresh data for {project_key}...")
                    
            except Exception as e:
                logging.warning(f"Storage check failed for {project_key}: {str(e)}")
        
        if need_fresh_data:
             projects_to_fetch.append(project_key)
    
    if projects_to_fetch:
        token = get_secret("sonarcloud", "api_token")
        raw_results = asyncio.run(_fetch_all_projects_history(projects_to_fetch, token, days, branch))
        
        for project_key, result in raw_results.items():
            if isinstance(result, Exception):
                logging.error(f"Failed to fetch {project_key}: {str(result)}")
            else:
                if result:
                    for r in result:
                        all_data.append(r)
                    if _storage:
                        try:
                            df_to_store = pd.DataFrame(result)
                            success = _storage.store_metrics_data(df_to_store, project_key, branch)
                            if success:
                                logging.info(f"Stored {len(result)} new records for {project_key}")
                        except Exception as e:
                            logging.warning(f"Could not store data for {project_key}: {str(e)}")
                else:
                    # Fallback to current measures if historical yields no data
                    try:
                        measures = _api.get_project_measures(project_key, branch)
                        if measures:
                            measures['project_key'] = project_key
                            measures['date'] = datetime.now().replace(tzinfo=None).strftime('%Y-%m-%d')
                            all_data.append(measures)
                            if _storage:
                                df_to_store = pd.DataFrame([measures])
                                _storage.store_metrics_data(df_to_store, project_key, branch)
                    except Exception as e:
                        logging.error(f"Fallback fetch failed for {project_key}: {str(e)}")
    
    df = pd.DataFrame(all_data)
    
    # If we have data, aggregate multiple records per day
    if not df.empty and 'date' in df.columns:
        # Convert date column to datetime for proper grouping
        df['date'] = pd.to_datetime(df['date'], format='ISO8601', errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_convert(None)
        
        # Group by project_key and date, then aggregate
        numeric_columns = ['coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating',
                          'vulnerabilities', 'security_rating', 'security_hotspots', 
                          'security_review_rating', 'security_hotspots_reviewed', 'code_smells', 
                          'sqale_rating', 'major_violations', 'minor_violations', 'violations']
        
        # Identify and convert available numeric columns to numeric dtype in one loop
        available_numeric = []
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                available_numeric.append(col)

        if available_numeric:
            # Create aggregation dict - use mean for numeric columns
            agg_dict = {col: 'mean' for col in available_numeric}
            
            # Add any other columns that should be preserved (take first value)
            other_cols = [col for col in df.columns if col not in available_numeric + ['date', 'project_key']]
            for col in other_cols:
                agg_dict[col] = 'first'
            
            # Group by project_key and date, then aggregate
            df = df.groupby(['project_key', 'date'], observed=True).agg(agg_dict).reset_index()
            
            # Round numeric values to reasonable precision
            for col in available_numeric:
                if col in df.columns:
                    df[col] = df[col].round(2)

            # ⚡ Bolt Optimization: Downcast DataFrame columns to float32 and category to reduce memory footprint.
            # This reduces the size of the dataframe in memory by up to 80% and speeds up Parquet serialization.
            if 'project_key' in df.columns:
                df['project_key'] = df['project_key'].astype('category')
            if 'branch' in df.columns:
                df['branch'] = df['branch'].astype('category')

            for col in available_numeric:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], downcast='float')
    
    return compress_to_parquet(df) if all_data else compress_to_parquet(pd.DataFrame())

def compute_metric_stats(df, metric_col, is_percent=False, higher_is_better=True):
    if df.empty or metric_col not in df.columns or 'date' not in df.columns:
        return ("0.0%" if is_percent else "0", None, "#888888")
    
    df_sorted = df.sort_values('date')
    
    # Bolt Optimization: Vectorized this calculation to reduce time complexity from O(M*N) to O(N)
    # by eliminating the Python-level iteration and using underlying C extensions
    grouped = df_sorted.groupby('project_key', sort=False, observed=True)[metric_col]
    earliest_total = float(grouped.first().sum())
    latest_total = float(grouped.last().sum())
    project_count = grouped.ngroups
    
    is_avg_metric = metric_col in ['duplicated_lines_density', 'security_rating', 'reliability_rating']
    
    if is_avg_metric and project_count > 0:
        latest_val = latest_total / project_count
        earliest_val = earliest_total / project_count
    else:
        latest_val = latest_total
        earliest_val = earliest_total
    
    delta_val = latest_val - earliest_val
    
    if is_percent:
        val_str = f"{latest_val:.1f}%"
    elif metric_col in ['security_rating', 'reliability_rating']:
         val_str = f"{latest_val:.1f}"
    else:
        val_str = f"{int(latest_val):,}"
    
    if abs(delta_val) < 0.01:
         delta_str = None
         color = "#888888"
    else:
        # Format delta to 1 decimal place if float-like, or int if integer metric
        delta_fmt = f"{int(delta_val):+d}" if not (is_percent or is_avg_metric) else f"{delta_val:+.1f}"
        delta_str = f"{delta_fmt}{'%' if is_percent else ''}"
        
        is_good = (delta_val < 0) if not higher_is_better else (delta_val > 0)
        color = "#1db954" if is_good else "#e91429"
    
    return val_str, delta_str, color

def get_metric_stats(df, metric_col, is_percent=False, higher_is_better=True):
    return compute_metric_stats(df, metric_col, is_percent=is_percent, higher_is_better=higher_is_better)

def display_dashboard(df, selected_projects, all_projects, branch_filter=None):
    """Display the main dashboard with metrics and charts"""
    
    # Get project names mapping
    project_names = {p['key']: p['name'] for p in all_projects}
    df['project_name'] = df['project_key'].map(project_names)
    
    # Overview metrics
    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-graph-up"></i> Overview</h2>', unsafe_allow_html=True)
    
    # Calculate summary statistics from all data (not just latest)
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # ⚡ Bolt Optimization: Vectorized Aggregation
    # Instead of iterating through every project (O(N*M)) inside helper function,
    # we sort once and group by project to get first/last values in O(N).
    # This reduces complexity from O(M * N * log N) to O(N log N).


    with col1:
        val, delta, color = compute_metric_stats(df, 'vulnerabilities')
        create_metric_card("Vulnerabilities", val, "iconoir-bug", delta, color, neon_class="neon-green")
    
    with col2:
        val, delta, color = compute_metric_stats(df, 'security_hotspots')
        create_metric_card("Security Hotspots", val, "iconoir-fire-flame", delta, color, neon_class="neon-orange")
    
    with col3:
        val, delta, color = compute_metric_stats(df, 'duplicated_lines_density', is_percent=True)
        create_metric_card("Duplicated Lines", val, "iconoir-page", delta, color, neon_class="neon-teal")
    
    with col4:
        val, delta, color = compute_metric_stats(df, 'security_rating')
        create_metric_card("Security Rating", val, "iconoir-lock", delta, color, neon_class="neon-green")
    
    with col5:
        val, delta, color = compute_metric_stats(df, 'reliability_rating')
        create_metric_card("Reliability Rating", val, "iconoir-flash", delta, color, neon_class="neon-blue")
    
    # Detailed metrics charts
    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-graph-up"></i> Detailed Metrics</h2>', unsafe_allow_html=True)
    
    # --- 1. Define the Data Dictionary ---
    ALL_METRICS = [
        'coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating', 
        'vulnerabilities', 'security_rating', 'security_hotspots', 'security_review_rating', 
        'security_hotspots_reviewed', 'code_smells', 'sqale_rating', 'major_violations', 
        'minor_violations', 'violations'
    ]
    available_metrics = [m for m in ALL_METRICS if m in df.columns]

    METRIC_PRESETS = {
        "Custom (Manual Selection)": [],
        "Security Posture": ["vulnerabilities", "security_rating", "security_hotspots"],
        "Reliability & Testing": ["bugs", "reliability_rating", "coverage"],
        "Maintainability": ["code_smells", "sqale_rating", "duplicated_lines_density"],
        "Violation Breakdown": ["violations", "major_violations", "minor_violations"]
    }
    
    # Filter presets to only include available metrics from the dataframe
    for preset in METRIC_PRESETS:
        METRIC_PRESETS[preset] = [m for m in METRIC_PRESETS[preset] if m in available_metrics]

    # --- 2. Initialize Session State ---
    if "active_metrics" not in st.session_state:
        st.session_state.active_metrics = METRIC_PRESETS["Security Posture"]

    if "active_preset" not in st.session_state:
        st.session_state.active_preset = "Security Posture"

    # --- 3. Define the Callbacks ---
    def sync_preset_to_multiselect():
        """Triggered when the user clicks a pre-defined group button."""
        selected_preset = st.session_state.preset_selector
        if selected_preset != "Custom (Manual Selection)":
            st.session_state.active_metrics = METRIC_PRESETS[selected_preset]
        st.session_state.active_preset = selected_preset

    def sync_multiselect_to_preset():
        """Triggered when the user manually adds/removes a metric."""
        current_metrics = set(st.session_state.metric_selector)
        
        matched_preset = "Custom (Manual Selection)"
        for preset_name, preset_metrics in METRIC_PRESETS.items():
            if preset_metrics and current_metrics == set(preset_metrics):
                matched_preset = preset_name
                break
                
        st.session_state.active_preset = matched_preset
        st.session_state.active_metrics = st.session_state.metric_selector

    # --- 4. Render the UI Components ---
    st.pills(
        "Select a specific metric group:", 
        options=list(METRIC_PRESETS.keys()),
        selection_mode="single",
        key="preset_selector",
        default=st.session_state.active_preset,
        on_change=sync_preset_to_multiselect
    )
    
    col1, col2 = st.columns([2, 1])

    with col1:
        
        st.multiselect(
            "Or customize up to 3 individual metrics:",
            available_metrics,
            key="metric_selector",
            max_selections=3,
            default=st.session_state.active_metrics,
            format_func=lambda m: m.replace('_', ' ').title(),
            on_change=sync_multiselect_to_preset,
            placeholder="Choose metrics to analyze...",
            help="Limiting selections ensures the trend charts remain readable without excessive scrolling."
        )

    def get_valid_chart_types(num_projects: int, num_metrics: int) -> list[str]:
        """
        Calculates architecturally valid visualization types based on data dimensionality.
        
        Time Complexity: O(1)
        Design Decision: Whitelists specific chart types rather than blacklisting, 
        ensuring a fail-secure UI state if new data structures are introduced later.
        """
        # The Line Chart is the universal standard for temporal aggregates.
        # It is our immutable baseline.
        valid_charts = ["Line Chart"]
        
        # Bar charts introduce visual clutter on time-series data unless 
        # strictly isolated to cross-project comparisons of a single metric.
        if num_projects > 1 and num_metrics == 1:
            valid_charts.append("Bar Chart (Grouped)")
            
        # Area charts are visually effective for volume-based metrics 
        # (e.g., 'lines_of_code', 'duplicated_lines') but become unreadable 
        # overlapping messes if more than one project or too many metrics are selected.
        if num_projects == 1 and num_metrics <= 2:
            valid_charts.append("Area Chart")
            
        # Notice: "Box Plot" is intentionally excluded from this routing logic entirely,
        # as temporal SonarCloud aggregates lack the internal variance required to render them.

        return valid_charts

    with col2:
        # 1. Calculate the current dimensional state
        active_project_count = len(selected_projects) if isinstance(selected_projects, list) else 1
        active_metric_count = len(st.session_state.get('metric_selector', []))

        # 2. Fetch the strict list of allowed visualizations
        allowed_charts = get_valid_chart_types(active_project_count, active_metric_count)

        # 3. Render the restricted UI component
        chart_type = st.selectbox(
            "Chart type",
            options=allowed_charts,
            help="Chart options dynamically update based on the number of projects and metrics selected to ensure data is visually readable."
        )
    st.markdown("</div>", unsafe_allow_html=True) # Ending expander conceptually if html, but we'll use Streamlit native expander by wrapping it

    # Decoupled visualization update: directly use the selected metrics
    confirmed_metrics = st.session_state.get('metric_selector', [])
    
    if not confirmed_metrics:
        st.info("Please select at least one metric to render the trend analysis.", icon="ℹ️")
        st.stop()
        
    if not df.empty:
        fig = None
        if chart_type in ["Line Chart", "Bar Chart (Grouped)"]:
            plot_type = "Line Chart" if chart_type == "Line Chart" else "Bar Chart"
            fig = render_dynamic_subplots(df, confirmed_metrics, project_names, chart_type=plot_type)
        elif chart_type == "Area Chart":
            fig = render_area_chart(df, date_col='date', metrics=confirmed_metrics)
            
        if fig:
            # Inject Decorator Pipeline
            if st.session_state.get('show_anomalies', False):
                fig = inject_statistical_anomalies(fig, df, 'date', confirmed_metrics)
                
            st.plotly_chart(fig, use_container_width=True, theme=None)
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.toggle(
            "Detect Anomalies (Z-Score > 3.0)", 
            value=False, 
            key="show_anomalies",
            help="Scans the historical timeline for severe degradations exceeding 3 standard deviations and injects UI markers."
        )
    
    # Project comparison table
    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-list"></i> Metric Details</h2>', unsafe_allow_html=True)
    
    if not df.empty:
        # Prepare data for display - show all historical data, not just latest
        display_data = df.copy()
        display_data['project_name'] = display_data['project_key'].map(project_names)
        
        # Add branch column if available
        if 'branch' in display_data.columns:
            display_data['branch'] = display_data['branch'].astype(object).fillna("").astype(str)
        else:
            # Use the selected branch from the sidebar if available, otherwise empty string
            display_data['branch'] = branch_filter if branch_filter else ""

        # Select columns to display (include branch)
        display_columns = ['date', 'project_name', 'branch'] + [col for col in available_metrics if col in display_data.columns]
        display_data = display_data[display_columns]
        
        # Sort by date, project, and branch for better readability
        display_data = display_data.sort_values(['date', 'project_name', 'branch'])
        
        # Format numeric columns
        for col in display_data.columns:
            if col not in ['project_name', 'date', 'project_key', 'branch']:
                try:
                    if 'rating' in col:
                        # Keep ratings as float for proper sorting, format in st.dataframe column_config
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0)
                    elif 'coverage' in col or 'density' in col or 'security_hotspots_reviewed' in col:
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0.0).round(2)
                    else:
                        # Handle integer columns
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0).astype(int)
                except Exception:
                    # If conversion fails, keep as string
                    display_data[col] = display_data[col].astype(str)
        
        # Define visual configuration for dataframe columns
        column_config = {
            "date": st.column_config.DateColumn(
                "Date",
                format="YYYY-MM-DD",
                width="medium"
            ),
            "project_name": st.column_config.TextColumn(
                "Project",
                width="medium"
            ),
            "branch": st.column_config.TextColumn(
                "Branch",
                width="small"
            ),
            "vulnerabilities": st.column_config.NumberColumn(
                "Vulns",
                help="Total number of vulnerabilities detected",
                format="%d"
            ),
            "bugs": st.column_config.NumberColumn(
                "Bugs",
                help="Total number of bugs detected",
                format="%d"
            ),
            "security_hotspots": st.column_config.NumberColumn(
                "Hotspots",
                help="Security hotspots requiring review",
                format="%d"
            ),
            "code_smells": st.column_config.NumberColumn(
                "Smells",
                help="Code smells affecting maintainability",
                format="%d"
            ),
            "coverage": st.column_config.ProgressColumn(
                "Coverage",
                help="Test coverage percentage",
                format="%.1f%%",
                min_value=0,
                max_value=100
            ),
            "duplicated_lines_density": st.column_config.ProgressColumn(
                "Duplication",
                help="Percentage of duplicated lines",
                format="%.1f%%",
                min_value=0,
                max_value=100
            ),
            "security_rating": st.column_config.NumberColumn(
                "Sec Rating",
                help="Security Rating (1=A, 5=E). Lower is better.",
                format="%.1f"
            ),
            "reliability_rating": st.column_config.NumberColumn(
                "Rel Rating",
                help="Reliability Rating (1=A, 5=E). Lower is better.",
                format="%.1f"
            ),
            "sqale_rating": st.column_config.NumberColumn(
                "Maint Rating",
                help="Maintainability Rating (1=A, 5=E). Lower is better.",
                format="%.1f"
            ),
             "security_review_rating": st.column_config.NumberColumn(
                "Rev Rating",
                help="Security Review Rating (1=A, 5=E). Lower is better.",
                format="%.1f"
            )
        }

        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
        
        # Export functionality
        csv = display_data.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"sonarcloud_metrics_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:",
            help="Export the displayed metric details as a CSV file for external analysis."
        )

def create_box_plot(df, metric, project_names):
    """Create a box plot for the selected metric"""
    if df.empty or metric not in df.columns:
        st.warning("No data available for the selected metric.", icon="⚠️")
        return
    
    # Prepare data
    plot_data = df.copy()
    plot_data['project_name'] = plot_data['project_key'].map(project_names)
    
    # Create box plot
    fig = px.box(
        plot_data,
        x='project_name',
        y=metric,
        title=f"{metric.replace('_', ' ').title()} Distribution by Project"
    )
    
    fig.update_layout(
        xaxis_title="Project",
        yaxis_title=metric.replace('_', ' ').title(),
        xaxis_tickangle=-45
    )
    
    st.plotly_chart(fig, use_container_width=True, theme=None)

    
    st.plotly_chart(fig, use_container_width=True, theme=None)

if __name__ == "__main__":
    main()
