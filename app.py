import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
from sonarcloud_api import SonarCloudAPI
from dashboard_components import create_metric_card, render_dynamic_subplots, render_area_chart, inject_statistical_anomalies
from azure_storage import AzureTableStorage
from dotenv import load_dotenv
from ui_styles import inject_custom_css
import asyncio
import aiohttp
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception

load_dotenv()

def load_css(file_name: str) -> None:
    """Reads a CSS file and injects it into the Streamlit DOM."""
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS file not found: {file_name}")
# Page configuration
st.set_page_config(
    page_title="SonarCloud Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize SonarCloud API
@st.cache_resource
def init_sonarcloud_api():
    # Load environment variables from a .env file if present
    
    token = os.getenv("SONARCLOUD_TOKEN", "")
    if not token:
        st.error("⚠️ SonarCloud token not found. Please set the SONARCLOUD_TOKEN environment variable.")
        st.stop()
    return SonarCloudAPI(token)

@st.cache_resource
def init_azure_storage():
    """Initialize Azure Table Storage client"""
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    if not connection_string:
        st.error("⚠️ Azure Storage connection string not found. Please set the AZURE_STORAGE_CONNECTION_STRING environment variable.")
        st.stop()
    return AzureTableStorage(connection_string)

# Main app
def main():
    inject_custom_css()
    load_css("styles.css")
    st.markdown('<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/iconoir-icons/iconoir@main/css/iconoir.css">', unsafe_allow_html=True)
    st.markdown('<h1 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-stats-report"></i> SonarCloud Dashboard</h1>', unsafe_allow_html=True)
    #st.markdown("Monitor and analyze your organization's code quality metrics")
    
    # Initialize API and storage
    api = init_sonarcloud_api()
    storage = init_azure_storage()
    
    # Sidebar for controls
    with st.sidebar:
        st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0;"><i class="iconoir-wrench"></i> Controls</h2>', unsafe_allow_html=True)
        
       
        organization = os.getenv("SONARCLOUD_ORG", "organization_key")
        
        # Date range selection
        st.markdown('<h3 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0;"><i class="iconoir-calendar"></i> Date Range</h3>', unsafe_allow_html=True)
        date_range = st.selectbox(
            "Select time period",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Last 6 months", "Last year"]
        )
        
        # Convert date range to days
        days_map = {
            "Last 7 days": 7,
            "Last 30 days": 30,
            "Last 90 days": 90,
            "Last 6 months": 180,
            "Last year": 365
        }
        days = days_map[date_range]

    
    # Fetch projects
    with st.spinner("Loading projects..."):
        projects = fetch_projects(api, organization)
        
    if not projects:
        st.error("No projects found or unable to fetch projects. Please check your organization key and permissions.")
        st.stop()
    
    # Project selection
    with st.sidebar:
        st.markdown('<h3 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0;"><i class="iconoir-building"></i> Project Selection</h3>', unsafe_allow_html=True)
        selected_project = st.selectbox(
            "Select a project to analyze",
            options=[p['key'] for p in projects],
            format_func=lambda x: next((p['name'] for p in projects if p['key'] == x), x)
        )
        
        if not selected_project:
            st.warning("Please select a project.")
            st.stop()
        
        # Get branches for the selected project
        project_branches = fetch_project_branches(api, selected_project)
        
        # Branch filter with actual branches from the selected project
        st.markdown('<h3 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0;"><i class="iconoir-git-branch"></i> Branch Filter</h3>', unsafe_allow_html=True)
        if project_branches:
            branch_options = [b.get('name', 'Unknown') for b in project_branches]
            branch_filter = st.selectbox(
                "Select branch (required)",
                options=branch_options,
                help="You must select a branch to continue."
            )
            if not branch_filter:
                st.warning("Please select a branch to continue.")
                st.stop()
        else:
            branch_filter = st.text_input(
            "Branch (required)",
            value="",
            help="No branches found. Enter branch name manually."
            )
            if not branch_filter:
                st.warning("Please enter a branch name to continue.")
                st.stop()
        
        # Execute Filter Button
        st.markdown('<h3 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0;"><i class="iconoir-search"></i> Execute Analysis</h3>', unsafe_allow_html=True)
        execute_analysis = st.button(
            "Load Data & Show Dashboard", 
            type="primary",
            help="Click to load data with selected filters and display dashboard",
            use_container_width=True
        )
        
        # Data Management Section (moved to bottom)
        st.markdown('<br><h3 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;"><i class="iconoir-database-script"></i> Data Management</h3>', unsafe_allow_html=True)
        
        if st.button("Refresh Data", help="Clear cache and fetch fresh data from SonarCloud", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
        try:
            if storage:
                stored_projects = storage.get_stored_projects()
                st.caption(f"**{len(stored_projects)}** projects in Azure Storage.")
                if len(stored_projects) >= storage.MAX_RETRIEVAL_LIMIT:
                    st.warning(f"Limit reached ({storage.MAX_RETRIEVAL_LIMIT}).")
        except Exception as e:
            st.caption(f"Storage unavailable: {str(e)}")
    
    # Only fetch and display data when execute button is clicked
    if execute_analysis:
        # Fetch metrics for selected project
        with st.status("Fetching telemetry from SonarCloud...", expanded=True) as status:
            metrics_data = fetch_metrics_data(api, [selected_project], days, branch_filter, storage)
            if metrics_data.empty:
                status.update(label="No metrics data available.", state="error", expanded=False)
                st.stop()
            status.update(label="Data successfully loaded!", state="complete", expanded=False)
        st.session_state['metrics_data'] = metrics_data
        st.session_state['data_project'] = selected_project
        st.session_state['data_branch'] = branch_filter
        
    # Use cached metrics_data if available
    metrics_data = st.session_state.get('metrics_data', pd.DataFrame())
    
    if not metrics_data.empty:
        # Main dashboard content
        data_project = st.session_state.get('data_project', selected_project)
        data_branch = st.session_state.get('data_branch', branch_filter)
        project_name = next((p['name'] for p in projects if p['key'] == data_project), data_project)
        
        # Single consolidated info block
        st.info(f"Showing records for project **{project_name}** | Branch: **{data_branch}**")
        
        display_dashboard(metrics_data, [data_project], projects, data_branch)
        
        # Debug: Show data info at the bottom
        st.markdown('---')
        with st.expander("Debug: Data Info"):
            st.write(f"Total records: {len(metrics_data)}")
            st.write(f"Date range: {metrics_data['date'].min()} to {metrics_data['date'].max()}")
            st.write(f"Unique dates: {metrics_data['date'].nunique()}")
            st.caption("Data has been aggregated by date - multiple records per day are averaged")
            st.dataframe(metrics_data.head())
    else:
        # Show instructions when no analysis is executed
        st.info("Select your filters in the sidebar and click 'Load Data & Show Dashboard' to begin analysis.")
        
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
        st.error(f"Error fetching projects: {str(e)}")
        return []

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_project_branches(_api, project_key):
    """Fetch branches for a specific project"""
    try:
        return _api.get_project_branches(project_key)
    except Exception as e:
        st.warning(f"Could not fetch branches for {project_key}: {str(e)}")
        return []

def should_retry_api_call(exc: Exception) -> bool:
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
async def fetch_sonar_history_async(session: aiohttp.ClientSession, project_key: str, token: str, days: int, branch: str = None) -> list:
    url = "https://sonarcloud.io/api/measures/search_history"
    start_date = datetime.now() - timedelta(days=days)
    end_date = datetime.now()
    
    metrics = [
        'coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating',
        'vulnerabilities', 'security_rating', 'security_hotspots', 'security_review_rating',
        'security_hotspots_reviewed', 'code_smells', 'sqale_rating', 'major_violations',
        'minor_violations', 'violations'
    ]
    params = {
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
        
        history = []
        if 'measures' in data:
            for measure in data['measures']:
                metric_name = measure['metric']
                for hist_item in measure.get('history', []):
                    date_val = hist_item.get('date')
                    value = hist_item.get('value')
                    
                    if date_val and value is not None:
                        record = next((r for r in history if r['date'] == date_val), None)
                        if not record:
                            record = {'date': date_val, 'project_key': project_key}
                            if branch:
                                record['branch'] = branch
                            history.append(record)
                        
                        if metric_name in ['coverage', 'duplicated_lines_density']:
                            record[metric_name] = float(value)
                        else:
                            record[metric_name] = int(float(value)) if '.' in value else int(value)
                            
        return history

async def _fetch_all_projects_history(project_keys: list, token: str, days: int, branch: str) -> dict:
    connector = aiohttp.TCPConnector(limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_sonar_history_async(session, pk, token, days, branch) for pk in project_keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return dict(zip(project_keys, results))

def fetch_metrics_data(_api, project_keys, days, branch=None, _storage=None):
    """Fetch metrics data for selected projects with Azure Table Storage integration"""
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
                        st.toast(f"Using stored records for {project_key} (latest: {coverage_info['latest_date']})", icon="📦")
                        all_data.extend(stored_data)
                        need_fresh_data = False
                else:
                    st.toast(f"Fetching fresh data for {project_key}...", icon="🔄")
                    
            except Exception as e:
                st.toast(f"Storage check failed for {project_key}: {str(e)}", icon="⚠️")
        
        if need_fresh_data:
             projects_to_fetch.append(project_key)
    
    if projects_to_fetch:
        token = os.getenv("SONARCLOUD_TOKEN", "")
        raw_results = asyncio.run(_fetch_all_projects_history(projects_to_fetch, token, days, branch))
        
        for project_key, result in raw_results.items():
            if isinstance(result, Exception):
                st.error(f"Failed to fetch {project_key}: {str(result)}")
            else:
                if result:
                    for r in result:
                        all_data.append(r)
                    if _storage:
                        try:
                            df_to_store = pd.DataFrame(result)
                            success = _storage.store_metrics_data(df_to_store, project_key, branch)
                            if success:
                                st.toast(f"Stored {len(result)} new records for {project_key}", icon="✅")
                        except Exception as e:
                            st.toast(f"Could not store data for {project_key}: {str(e)}", icon="⚠️")
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
                        st.error(f"Fallback fetch failed for {project_key}: {str(e)}")
    
    df = pd.DataFrame(all_data)
    
    # If we have data, aggregate multiple records per day
    if not df.empty and 'date' in df.columns:
        # Convert date column to datetime for proper grouping
        df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce', utc=True)
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
            df = df.groupby(['project_key', 'date']).agg(agg_dict).reset_index()
            
            # Round numeric values to reasonable precision
            for col in available_numeric:
                if col in df.columns:
                    df[col] = df[col].round(2)
    
    return df if all_data else pd.DataFrame()

def display_dashboard(df, selected_projects, all_projects, branch_filter=None):
    """Display the main dashboard with metrics and charts"""
    
    # Get project names mapping
    project_names = {p['key']: p['name'] for p in all_projects}
    
    # Overview metrics
    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-graph-up"></i> Overview</h2>', unsafe_allow_html=True)
    
    # Calculate summary statistics from all data (not just latest)
    col1, col2, col3, col4, col5 = st.columns(5)
    
    def get_metric_stats(df, col, higher_is_better=False, is_percent=False):
        """Helper to calculate current value and delta trend."""
        if col not in df.columns:
            return "0", None, None

        df_sorted = df.sort_values('date')
        if df_sorted.empty:
            return "0", None, None

        projects = df_sorted['project_key'].unique()
        latest_val = 0.0
        earliest_val = 0.0

        for p in projects:
            p_data = df_sorted[df_sorted['project_key'] == p]
            if not p_data.empty:
                latest_val += float(p_data.iloc[-1][col])
                earliest_val += float(p_data.iloc[0][col])

        is_avg_metric = col in ['duplicated_lines_density', 'security_rating', 'reliability_rating']
        if is_avg_metric and len(projects) > 0:
            latest_val /= len(projects)
            earliest_val /= len(projects)

        delta_val = latest_val - earliest_val

        if is_percent:
            val_str = f"{latest_val:.1f}%"
        elif col in ['security_rating', 'reliability_rating']:
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

    with col1:
        val, delta, color = get_metric_stats(df, 'vulnerabilities')
        create_metric_card("Vulnerabilities", val, "iconoir-shield-warning", delta, color)
    
    with col2:
        val, delta, color = get_metric_stats(df, 'security_hotspots')
        create_metric_card("Security Hotspots", val, "iconoir-fire-flame", delta, color)
    
    with col3:
        val, delta, color = get_metric_stats(df, 'duplicated_lines_density', is_percent=True)
        create_metric_card("Duplicated Lines", val, "iconoir-page", delta, color)
    
    with col4:
        val, delta, color = get_metric_stats(df, 'security_rating')
        create_metric_card("Security Rating", val, "iconoir-lock", delta, color)
    
    with col5:
        val, delta, color = get_metric_stats(df, 'reliability_rating')
        create_metric_card("Reliability Rating", val, "iconoir-flash", delta, color)
    
    # Detailed metrics charts
    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-bar-chart"></i> Detailed Metrics</h2>', unsafe_allow_html=True)
    
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
        st.info("Please select at least one metric to render the trend analysis.")
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
                
            st.plotly_chart(fig, use_container_width=True)
            
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
            display_data['branch'] = display_data['branch'].fillna("").astype(str)
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
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0).astype(str)
                    elif 'coverage' in col or 'density' in col or 'security_hotspots_reviewed' in col:
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0.0).round(2)
                    else:
                        # Handle integer columns
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0).astype(int)
                except Exception:
                    # If conversion fails, keep as string
                    display_data[col] = display_data[col].astype(str)
        
        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True
        )
        
        # Export functionality
        csv = display_data.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"sonarcloud_metrics_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

def create_box_plot(df, metric, project_names):
    """Create a box plot for the selected metric"""
    if df.empty or metric not in df.columns:
        st.warning("No data available for the selected metric.")
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
    
    st.plotly_chart(fig, use_container_width=True)

    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
