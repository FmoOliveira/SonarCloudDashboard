import streamlit as st
from datetime import datetime, timedelta
from ui_styles import render_theme_toggle
from auth_manager import do_logout
from data_service import fetch_project_branches
from html_factory import get_profile_photo_html, get_profile_initials_html, get_profile_name_html, get_heading_html

def _release_memory_safely(*session_keys: str) -> None:
    keys_deleted = False
    for key in session_keys:
        if key in st.session_state:
            del st.session_state[key]

def handle_project_change():
    _release_memory_safely('metrics_data_parquet', 'data_project', 'data_branch', 'show_anomalies')
    if 'metric_selector' in st.session_state:
        st.session_state['metric_selector'] = ["vulnerabilities", "security_rating"]

def render_profile(cookies, safe_user_name, safe_photo_b64, safe_initials, safe_popover_label):
    with st.popover(safe_popover_label):
        if safe_photo_b64:
            st.markdown(get_profile_photo_html(safe_photo_b64), unsafe_allow_html=True)
        else:
            st.markdown(get_profile_initials_html(safe_initials), unsafe_allow_html=True)
        
        st.markdown(get_profile_name_html(safe_user_name), unsafe_allow_html=True)
        
        render_theme_toggle(cookies)
        
        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True, type="primary", icon=":material/logout:"):
            do_logout(cookies)

def render_sidebar(is_demo_mode: bool, projects: list, cookies, safe_user_name, safe_photo_b64, safe_initials, safe_popover_label) -> tuple:
    with st.sidebar:
        render_profile(cookies, safe_user_name, safe_photo_b64, safe_initials, safe_popover_label)
        
        st.markdown(get_heading_html("Controls", "iconoir-settings", top_margin=True), unsafe_allow_html=True)
        
        project_names = {p.key: p.name for p in projects}

        selected_project = st.selectbox(
            "Project",
            options=[p.key for p in projects],
            format_func=lambda x: project_names.get(x, x),
            on_change=handle_project_change,
            help="Select a repository to view its metrics."
        )
        
        if is_demo_mode:
            branch_options = ["main"]
        else:
            branches = fetch_project_branches(selected_project)
            branch_options = [b.name for b in branches]

        date_range = st.selectbox("Time Period", options=["Last 7 days", "Last 30 days", "Last 90 days", "Last year", "Custom..."], index=1)

        custom_days = None
        disable_submit = False
        if date_range == "Custom...":
            date_vals = st.date_input(
                "Select Date Range",
                value=(datetime.now() - timedelta(days=30), datetime.now()),
                max_value=datetime.now(),
                label_visibility="collapsed",
                format="YYYY/MM/DD",
                help="Select the start and end dates."
            )
            if isinstance(date_vals, tuple) and len(date_vals) == 2:
                start_date, end_date = date_vals
                custom_days = (datetime.now().date() - start_date).days
                custom_days = max(1, custom_days)
            elif isinstance(date_vals, tuple) and len(date_vals) == 1:
                st.info("Please select an end date to complete the range.", icon="📅")
                disable_submit = True
                custom_days = 30
            else:
                custom_days = 30

        days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "Last year": 365}.get(date_range, custom_days if date_range == "Custom..." else 30)

        with st.form(key="controls_form", border=False):
            if branch_options:
                branch_filter = st.selectbox("Branch", options=branch_options, help="Select a branch to analyze.")
            else:
                branch_filter = st.text_input("Branch", value="master", help="No branches found. Enter branch name manually.", placeholder="e.g., main, master, feature/xyz")
            execute_analysis = st.form_submit_button("Load Dashboard", type="primary", use_container_width=True, icon=":material/analytics:", disabled=disable_submit)

        if st.button("Refresh Data", use_container_width=True, icon=":material/sync:"):
            st.cache_data.clear()
            st.rerun()
            
    return selected_project, branch_filter, days, execute_analysis, project_names
