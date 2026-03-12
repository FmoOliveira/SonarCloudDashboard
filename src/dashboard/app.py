import streamlit as st

# Backward-compatibility monkey-patch for unmaintained third-party plugins using deprecated st.cache
if hasattr(st, 'cache'):
    def _safe_cache(*args, **kwargs):
        kwargs.pop('suppress_st_warning', None)
        kwargs.pop('allow_output_mutation', None)
        kwargs.pop('hash_funcs', None)
        return st.cache_data(*args, **kwargs)
    st.cache = _safe_cache

import pandas as pd
import html
import os
import secrets
import gc
import sys
import secrets
from streamlit_cookies_manager import CookieManager

from sonarcloud_api import SonarCloudAPI
from database.factory import get_storage_client
from auth import get_auth_url, acquire_token_by_auth_code, logout, get_user_photo
from dashboard_components import decompress_from_parquet

# New modular imports
from data_service import (
    get_secret, 
    fetch_projects, 
    fetch_project_branches, 
    fetch_metrics_data
)
from dashboard_view import display_dashboard, render_login_page
from ui_styles import (
    load_css, 
    inject_custom_css, 
    apply_theme_overrides, 
    render_theme_toggle
)

# Page configuration
st.set_page_config(
    page_title="SonarCloud Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

def release_memory_safely(*session_keys: str) -> None:
    """Safely deletes large objects from the Streamlit session state and forces GC."""
    keys_deleted = False
    for key in session_keys:
        if key in st.session_state:
            del st.session_state[key]
            keys_deleted = True
    if keys_deleted:
        gc.collect()

def handle_project_change():
    """Callback triggered when the user changes the project dropdown."""
    release_memory_safely('metrics_data_parquet', 'data_project', 'data_branch', 'show_anomalies')
    if 'metric_selector' in st.session_state:
        st.session_state['metric_selector'] = ["vulnerabilities", "security_rating"]

@st.cache_resource
def init_sonarcloud_api():
    token = get_secret("sonarcloud", "api_token")
    return SonarCloudAPI(token)

@st.cache_resource
def init_storage_client():
    return get_storage_client()

def main():
    inject_custom_css()
    load_css("styles.css")
    if "theme_toggle" not in st.session_state:
        st.session_state.theme_toggle = False
    apply_theme_overrides()
    st.markdown('<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/iconoir-icons/iconoir@main/css/iconoir.css">', unsafe_allow_html=True)
    
    cookies = CookieManager()
    if not cookies.ready():
        st.stop()
        
    auth_token = cookies.get("auth_token")
    
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

        with st.spinner("Authenticating..."):
            token_result = acquire_token_by_auth_code(auth_code)

            # Clean up state cookie after successful validation
            del cookies["auth_state"]
            cookies.save()
            if "access_token" in token_result:
                auth_token = token_result["access_token"]
                cookies["auth_token"] = auth_token
                user_info = token_result.get("id_token_claims", {})
                cookies["user_info_name"] = user_info.get("name", "User")
                photo_b64 = get_user_photo(auth_token)
                if photo_b64:
                    cookies["user_photo"] = photo_b64
                cookies.save()
            else:
                error_desc = token_result.get("error_description", "Unknown error")
                if "AADSTS54005" in error_desc:
                    st.rerun()
                else:
                    error_msg = f"Authentication failed: {error_desc}"
                    st.error(error_msg, icon="🚨")
                    st.stop()

    if auth_token:
        user_name = cookies.get("user_info_name") or "User"
        initials = "".join([n[0] for n in user_name.split() if n])[:2].upper() or "U"
        safe_user_name = html.escape(user_name)
        safe_initials = html.escape(initials)
        safe_photo_b64 = html.escape(cookies.get("user_photo") or "")
        safe_popover_label = html.escape(f"👤 {user_name.split()[0]}" if user_name != "User" else "👤 Profile")
        st.markdown('<h1 style="display: flex; align-items: center; gap: 0.5rem; margin: 0; padding-bottom: 2rem;"><i class="iconoir-stats-report"></i> SonarCloud Dashboard</h1>', unsafe_allow_html=True)
    else:
        st.markdown('<h1 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-stats-report"></i> SonarCloud Dashboard</h1>', unsafe_allow_html=True)

        state = cookies.get("auth_state")
        if not state:
            state = secrets.token_urlsafe(32)
            cookies["auth_state"] = state
            cookies.save()

        auth_url = get_auth_url(state=state)
        with st.sidebar:
            render_theme_toggle()
        
        # Render prominent login page in main content area
        render_login_page(auth_url)
        st.stop()
            
    is_demo_mode = "--demo-mode" in sys.argv
    if is_demo_mode:
        st.sidebar.warning("🛠️ Demo Mode")
        api, storage, organization = None, None, "demo-org"
        projects = [{"key": "demo-project-alpha", "name": "Frontend Web Application"}]
    else:
        api = init_sonarcloud_api()
        storage = init_storage_client()
        organization = get_secret("sonarcloud", "organization_key")
        with st.spinner("Loading projects..."):
            projects = fetch_projects(api, organization)
        if not projects:
            st.error("No projects found.", icon="🚨")
            st.stop()

    with st.sidebar:
        with st.popover(safe_popover_label):
            if safe_photo_b64:
                st.markdown(f'<div style="text-align: center;"><img src="{safe_photo_b64}" style="width: 64px; height: 64px; border-radius: 50%;"></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="text-align: center;"><div style="width: 64px; height: 64px; margin: 0 auto; border-radius: 50%; background: #1db954; color: white; display: flex; justify-content: center; align-items: center; font-weight: 700;">{safe_initials}</div></div>', unsafe_allow_html=True)
            
            st.markdown(f"<p style='text-align: center; margin-top: 10px; margin-bottom: 10px;'><strong>{safe_user_name}</strong></p>", unsafe_allow_html=True)
            
            # Theme toggle moved inside the Profile menu
            render_theme_toggle()
            
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            
            if st.button("Logout", use_container_width=True, type="primary", icon=":material/logout:"):
                logout(cookies)
        
        st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem;"><i class="iconoir-settings"></i> Controls</h2>', unsafe_allow_html=True)
        
        # ⚡ Bolt Optimization: Map projects list to a dictionary for O(1) format_func
        # lookup in the Streamlit render loop. The old `next(generator)` was O(M*N).
        project_names = {p['key']: p['name'] for p in projects}

        selected_project = st.selectbox(
            "Project",
            options=[p['key'] for p in projects],
            format_func=lambda x: project_names.get(x, x),
            on_change=handle_project_change
        )
        
        if is_demo_mode:
            branch_options = ["main"]
        else:
            branches = fetch_project_branches(api, selected_project)
            branch_options = [b.get('name', 'Unknown') for b in branches]

        with st.form(key="controls_form", border=False):
            date_range = st.selectbox("Time Period", options=["Last 7 days", "Last 30 days", "Last 90 days", "Last year", "Custom..."], index=1)
            days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "Last year": 365}.get(date_range, 30)
            branch_filter = st.selectbox("Branch", options=branch_options, help="Select a branch to analyze.") if branch_options else "master"
            execute_analysis = st.form_submit_button("Load Dashboard", type="primary", use_container_width=True, icon=":material/analytics:")

        if st.button("Refresh Data", use_container_width=True, icon=":material/sync:"):
            st.cache_data.clear()
            st.rerun()

    if execute_analysis:
        with st.status("Loading telemetry...", expanded=True) as status:
            if is_demo_mode:
                demo_path = os.path.join(os.path.dirname(__file__), "demo", "demo_metrics.parquet")
                _ = pd.read_parquet(demo_path) if os.path.exists(demo_path) else pd.DataFrame()
                st.session_state['metrics_data_parquet'] = b"" # simplified for demo
            else:
                st.session_state['metrics_data_parquet'] = fetch_metrics_data(api, [selected_project], days, branch_filter, storage)
            st.session_state['data_project'] = selected_project
            st.session_state['data_branch'] = branch_filter
            status.update(label="Telemetry loaded successfully!", state="complete", expanded=False)

    if 'metrics_data_parquet' in st.session_state:
        metrics_data = decompress_from_parquet(st.session_state['metrics_data_parquet'])
        if not metrics_data.empty:
            display_dashboard(metrics_data, [st.session_state['data_project']], projects, st.session_state['data_branch'])
        else:
            st.info("No metrics data available for the selected filters. Please try adjusting the time period or branch.", icon="🔍")
    else:
        st.info("Select filters and click **Load Dashboard** to begin analysis.", icon="👋")

if __name__ == "__main__":
    main()
