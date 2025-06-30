import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
from sonarcloud_api import SonarCloudAPI
from dashboard_components import create_metric_card, create_trend_chart, create_comparison_chart
from azure_storage import AzureTableStorage
from dotenv import load_dotenv

load_dotenv()

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
    st.title("📊 SonarCloud Dashboard")
    #st.markdown("Monitor and analyze your organization's code quality metrics")
    
    # Initialize API and storage
    api = init_sonarcloud_api()
    storage = init_azure_storage()
    
    # Sidebar for controls
    with st.sidebar:
        st.header("🔧 Controls")
        
       
        organization = os.getenv("SONARCLOUD_ORG", "organization_key")
        
        # Date range selection
        st.subheader("📅 Date Range")
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
        st.subheader("🏗️ Project Selection")
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
        st.subheader("🌿 Branch Filter")
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
        st.subheader("🔍 Execute Analysis")
        execute_analysis = st.button(
            "📊 Load Data & Show Dashboard", 
            type="primary",
            help="Click to load data with selected filters and display dashboard",
            use_container_width=True
        )
        
        # Data Management Section (moved to bottom)
        st.subheader("💾 Data Management")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Refresh Data", help="Clear cache and fetch fresh data from SonarCloud"):
                st.cache_data.clear()
                st.rerun()
        
        with col2:
            stored_projects = []
            try:
                stored_projects = storage.get_stored_projects()
                st.info(f"📊 {len(stored_projects)} projects in storage")
            except Exception as e:
                st.warning(f"Storage status unavailable: {str(e)}")
    
    # Only fetch and display data when execute button is clicked
    if execute_analysis:
        # Fetch metrics for selected project
        with st.spinner("Loading metrics data..."):
            metrics_data = fetch_metrics_data(api, [selected_project], days, branch_filter, storage)
        if metrics_data.empty:
            st.error("No metrics data available for the selected project and time period.")
            st.stop()
        st.session_state['metrics_data'] = metrics_data
    # Use cached metrics_data if available
    metrics_data = st.session_state.get('metrics_data', pd.DataFrame())
    if not metrics_data.empty and execute_analysis:
        # Debug: Show data info
        with st.expander("Debug: Data Info"):
            st.write(f"Total records: {len(metrics_data)}")
            st.write(f"Date range: {metrics_data['date'].min()} to {metrics_data['date'].max()}")
            st.write(f"Unique dates: {metrics_data['date'].nunique()}")
            st.info("📊 Data has been aggregated by date - multiple records per day are averaged")
            st.dataframe(metrics_data.head())
        # Show active filters
        project_name = next((p['name'] for p in projects if p['key'] == selected_project), selected_project)
        st.info(f"📊 Analyzing project: **{project_name}**")
        if branch_filter:
            st.info(f"📋 Showing data for branch: **{branch_filter}**")
    # Main dashboard content
    if not metrics_data.empty:
        display_dashboard(metrics_data, [selected_project], projects, execute_analysis, branch_filter)
    else:
        # Show instructions when no analysis is executed
        st.info("👈 Select your filters in the sidebar and click 'Load Data & Show Dashboard' to begin analysis.")
        
        # Show summary of available options
        if projects:
            st.subheader("📋 Available Projects")
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

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_metrics_data(_api, project_keys, days, branch=None, _storage=None):
    """Fetch metrics data for selected projects with Azure Table Storage integration"""
    all_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, project_key in enumerate(project_keys):
        status_text.text(f"Fetching data for {project_key}...")
        
        # First check if we have sufficient data coverage in Azure Table Storage
        need_fresh_data = True
        
        if _storage:
            try:
                coverage_info = _storage.check_data_coverage(project_key, branch, days)
                
                if coverage_info["has_coverage"]:
                    # We have sufficient data coverage, use stored data
                    stored_data = _storage.retrieve_metrics_data(project_key, branch, days)
                    if stored_data:
                        st.info(f"✅ Using {coverage_info['record_count']} stored records for {project_key} (latest: {coverage_info['latest_date']})")
                        all_data.extend(stored_data)
                        need_fresh_data = False
                else:
                    st.info(f"📅 {coverage_info['reason']} - fetching fresh data for {project_key}")
                    
            except Exception as e:
                st.warning(f"Could not check stored data coverage for {project_key}: {str(e)}")
        
        # If no sufficient stored data or storage is not available, fetch from SonarCloud API
        if need_fresh_data:
            try:
                # Get historical data first (this is the main data for time series)
                history = _api.get_project_history(project_key, days, branch)
                if history:
                    for record in history:
                        record['project_key'] = project_key
                        all_data.append(record)
                    
                    # Store the fetched data in Azure Table Storage
                    if _storage and history:
                        try:
                            df_to_store = pd.DataFrame(history)
                            df_to_store['project_key'] = project_key
                            success = _storage.store_metrics_data(df_to_store, project_key, branch)
                            if success:
                                st.success(f"📊 Stored {len(history)} new records for {project_key}")
                        except Exception as e:
                            st.warning(f"Could not store data for {project_key}: {str(e)}")
                
                # Only get current measures if no historical data is available
                if not history:
                    measures = _api.get_project_measures(project_key, branch)
                    if measures:
                        measures['project_key'] = project_key
                        measures['date'] = datetime.now().replace(tzinfo=None).strftime('%Y-%m-%d')
                        all_data.append(measures)
                        
                        # Store current measures if no history available
                        if _storage:
                            try:
                                df_to_store = pd.DataFrame([measures])
                                success = _storage.store_metrics_data(df_to_store, project_key, branch)
                                if success:
                                    st.success(f"📊 Stored current measures for {project_key}")
                            except Exception as e:
                                st.warning(f"Could not store current measures for {project_key}: {str(e)}")
                        
            except Exception as e:
                st.warning(f"Could not fetch data for {project_key}: {str(e)}")
        
        progress_bar.progress((i + 1) / len(project_keys))
    
    progress_bar.empty()
    status_text.empty()
    
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

def display_dashboard(df, selected_projects, all_projects, execute_analysis, branch_filter=None):
    """Display the main dashboard with metrics and charts"""
    
    # Get project names mapping
    project_names = {p['key']: p['name'] for p in all_projects}
    
    # Overview metrics
    st.header("📈 Overview")
    
    # Calculate summary statistics from all data (not just latest)
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_vulnerabilities = df['vulnerabilities'].fillna(0).astype(int).sum() if 'vulnerabilities' in df.columns else 0
        create_metric_card("Sum of Vulnerabilities", str(total_vulnerabilities), "🛡️")
    
    with col2:
        total_security_hotspots = df['security_hotspots'].fillna(0).astype(int).sum() if 'security_hotspots' in df.columns else 0
        create_metric_card("Sum of Security Hotspots", str(total_security_hotspots), "🔥")
    
    with col3:
        sum_duplicated_density = df['duplicated_lines_density'].fillna(0).astype(float).sum() if 'duplicated_lines_density' in df.columns else 0
        create_metric_card("Sum of Duplicated Lines Density", f"{sum_duplicated_density:.1f}%", "📋")
    
    with col4:
        avg_security_rating = df['security_rating'].fillna(0).astype(float).mean() if 'security_rating' in df.columns else 0
        create_metric_card("Average Security Rating", f"{avg_security_rating:.1f}", "🔒")
    
    with col5:
        avg_reliability_rating = df['reliability_rating'].fillna(0).astype(float).mean() if 'reliability_rating' in df.columns else 0
        create_metric_card("Average Reliability Rating", f"{avg_reliability_rating:.1f}", "⚡")
    
    # Detailed metrics charts
    st.header("📊 Detailed Metrics")
    
    # Metrics selection
    available_metrics = [
        'coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating',
        'vulnerabilities', 'security_rating', 'security_hotspots', 
        'security_review_rating', 'security_hotspots_reviewed', 'code_smells', 
        'sqale_rating', 'major_violations', 'minor_violations', 'violations'
    ]
    available_metrics = [m for m in available_metrics if m in df.columns]

    col1, col2 = st.columns(2)

    with col1:
        # Pre-selected key metrics
        key_metrics = ['vulnerabilities', 'security_hotspots', 'duplicated_lines_density', 
                      'bugs', 'security_rating', 'reliability_rating']
        default_metrics = [m for m in key_metrics if m in available_metrics]
        if 'selected_metrics' not in st.session_state:
            st.session_state['selected_metrics'] = default_metrics
        if 'temp_selected_metrics' not in st.session_state:
            st.session_state['temp_selected_metrics'] = st.session_state['selected_metrics']
        # Use a callback to update selected_metrics without triggering a refresh
        def update_selected_metrics():
            st.session_state['selected_metrics'] = st.session_state['temp_selected_metrics']
        st.multiselect(
            "Select metrics to visualize",
            available_metrics,
            key="temp_selected_metrics",
            on_change=update_selected_metrics
        )
        st.caption("Changing metrics here will not update the dashboard until you click 'Load Data & Show Dashboard'.")

    with col2:
        chart_type = st.selectbox(
            "Chart type",
            ["Line Chart", "Bar Chart", "Box Plot"]
        )

    # Only update dashboard when button is clicked
    if 'confirmed_metrics' not in st.session_state:
        st.session_state['confirmed_metrics'] = st.session_state['selected_metrics']
    if execute_analysis:
        st.session_state['confirmed_metrics'] = st.session_state['selected_metrics']
    confirmed_metrics = st.session_state['confirmed_metrics']
    if confirmed_metrics and not df.empty:
        if len(confirmed_metrics) == 1:
            # Single metric - use existing chart functions
            selected_metric = confirmed_metrics[0]
            if chart_type == "Line Chart":
                create_trend_chart(df, selected_metric, project_names)
            elif chart_type == "Bar Chart":
                create_comparison_chart(df, selected_metric, project_names)
            elif chart_type == "Box Plot":
                create_box_plot(df, selected_metric, project_names)
        else:
            # Multiple metrics - create multi-metric chart
            create_multi_metric_chart(df, confirmed_metrics, project_names, chart_type)
    
    # Project comparison table
    st.header("📋 Metric Details")
    
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
                except Exception as e:
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
            label="📥 Download as CSV",
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

def create_multi_metric_chart(df, metrics, project_names, chart_type):
    """Create a chart with multiple metrics"""
    if df.empty or not metrics:
        st.warning("No data available for the selected metrics.")
        return
    
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    
    # Prepare data
    plot_data = df.copy()
    plot_data['project_name'] = plot_data['project_key'].map(project_names)
    
    if chart_type == "Line Chart":
        # Convert date column
        if 'date' in plot_data.columns:
            try:
                plot_data['date'] = pd.to_datetime(plot_data['date'], format='mixed', utc=True)
                plot_data['date'] = plot_data['date'].dt.tz_convert(None)
                plot_data = plot_data.sort_values('date')
            except Exception as e:
                st.warning(f"Could not parse dates: {str(e)}")
                return
        else:
            st.warning("No date information available for trend analysis.")
            return
        
        # Create multi-metric line chart
        fig = go.Figure()
        
        for metric in metrics:
            if metric in plot_data.columns:
                fig.add_trace(go.Scatter(
                    x=plot_data['date'],
                    y=plot_data[metric],
                    mode='lines+markers',
                    name=metric.replace('_', ' ').title(),
                    line=dict(width=2)
                ))
        
        fig.update_layout(
            title=f"Multiple Metrics Trend Over Time",
            xaxis_title="Date",
            yaxis_title="Values",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500
        )
        
    else:
        st.info("Multi-metric view is currently available for Line Charts only. Please select Line Chart or choose a single metric for other chart types.")
        return
    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
