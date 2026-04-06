import streamlit as st

# Backward-compatibility monkey-patch for unmaintained third-party plugins using deprecated st.cache
if hasattr(st, 'cache'):
    def _safe_cache(*args, **kwargs):
        kwargs.pop('suppress_st_warning', None)
        kwargs.pop('allow_output_mutation', None)
        kwargs.pop('hash_funcs', None)
        return st.cache_data(*args, **kwargs)
    st.cache = _safe_cache

import logging
import pandas as pd
import html
import os
import sys
from streamlit_cookies_manager import CookieManager

from database.factory import get_storage_client
from dashboard_components import decompress_from_parquet

from data_service import fetch_projects, fetch_metrics_data
from dashboard_view import display_dashboard, render_login_page
from ui_styles import load_css, inject_custom_css, apply_theme_overrides, render_theme_toggle
from sidebar_controller import render_sidebar
from auth_manager import handle_auth, get_user_info, get_login_url

st.set_page_config(
    page_title="SonarCloud Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)



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
        
    auth_token = handle_auth(cookies)
    
    is_demo_mode = "--demo-mode" in sys.argv or os.environ.get("DEMO_MODE") == "1"

    if auth_token:
        user_name, raw_photo_b64 = get_user_info(cookies)
        if not user_name: user_name = "User"
        if not raw_photo_b64: raw_photo_b64 = ""
        
        initials = "".join([n[0] for n in user_name.split() if n])[:2].upper() or "U"
        safe_user_name = html.escape(user_name)
        safe_initials = html.escape(initials)

        if raw_photo_b64 and not raw_photo_b64.startswith(("data:image/", "https://")):
            raw_photo_b64 = ""

        safe_photo_b64 = html.escape(raw_photo_b64)
        safe_popover_label = html.escape(f"👤 {user_name.split()[0]}" if user_name != "User" else "👤 Profile")
        st.markdown('<h1 style="display: flex; align-items: center; gap: 0.5rem; margin: 0; padding-bottom: 2rem;"><i class="iconoir-stats-report"></i> SonarCloud Dashboard</h1>', unsafe_allow_html=True)
    else:
        st.markdown('<h1 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-stats-report"></i> SonarCloud Dashboard</h1>', unsafe_allow_html=True)

        if not is_demo_mode:
            auth_url = get_login_url(cookies)
            with st.sidebar:
                render_theme_toggle()

            render_login_page(auth_url)
            st.stop()
        else:
            safe_user_name = "Demo User"
            safe_initials = "DU"
            safe_photo_b64 = ""
            safe_popover_label = "👤 Demo User"
            
    if is_demo_mode:
        st.sidebar.warning("🛠️ Demo Mode", icon="⚠️")
        storage, organization = None, "demo-org"
        from models import SonarProject
        projects = [SonarProject(key="demo-project-alpha", name="Frontend Web Application")]
    else:
        try:
            storage = init_storage_client()
            from config import config
            organization = config.sonarcloud_organization_key
            with st.spinner("Loading projects..."):
                projects = fetch_projects(organization)
            if not projects:
                st.error("No projects found or unable to fetch projects. Please check your organization key and permissions.", icon="🚨")
                st.stop()
        except Exception as e:
            st.error(f"Failed to initialize data layer: {e}", icon="🚨")
            st.stop()

    selected_project, branch_filter, days, execute_analysis, project_names = render_sidebar(
        is_demo_mode, projects, cookies, safe_user_name, safe_photo_b64, safe_initials, safe_popover_label
    )

    if execute_analysis:
        with st.status("Loading telemetry...", expanded=True) as status:
            if is_demo_mode:
                demo_path = os.path.join(os.path.dirname(__file__), "demo", "demo_metrics.parquet")
                _ = pd.read_parquet(demo_path) if os.path.exists(demo_path) else pd.DataFrame()
                st.session_state['metrics_data_parquet'] = b"" 
                compressed_bytes = b""
            else:
                try:
                    compressed_bytes = fetch_metrics_data([selected_project], days, branch_filter, storage)
                except Exception as e:
                    st.error(f"Error fetching metrics: {e}", icon="🚨")
                    compressed_bytes = b""

            if not compressed_bytes:
                status.update(label="No data found.", state="complete", expanded=False)
                st.session_state['metrics_data_parquet'] = b""
            else:
                st.session_state['metrics_data_parquet'] = compressed_bytes
                status.update(label="Telemetry loaded successfully!", state="complete", expanded=False)
                st.toast("Data successfully loaded!", icon="✅")

            st.session_state['data_project'] = selected_project
            st.session_state['data_branch'] = branch_filter

    if 'metrics_data_parquet' in st.session_state:
        metrics_data = decompress_from_parquet(st.session_state['metrics_data_parquet'])
        if not metrics_data.empty:
            data_project = st.session_state['data_project']
            data_branch = st.session_state['data_branch']
            project_name = project_names.get(data_project, data_project)
            st.info(f"Showing records for project **{project_name}** | Branch: **{data_branch}**", icon="📋")
            display_dashboard(metrics_data, [data_project], projects, data_branch)

            del metrics_data
        else:
            st.info("No metrics data available for the selected filters. Please try adjusting the time period or branch.", icon="🔍")
    else:
        st.info("Select filters and click **Load Dashboard** to begin analysis.", icon="👋")

if __name__ == "__main__":
    main()
