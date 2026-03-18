import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from dashboard_components import (
    create_metric_card, 
    render_dynamic_subplots, 
    render_area_chart, 
    inject_statistical_anomalies
)

def compute_metric_stats(earliest_vals, latest_vals, project_count, metric_col, is_percent=False, higher_is_better=True):
    if metric_col not in earliest_vals.columns or project_count == 0:
        return ("0.0%" if is_percent else "0", None, "#888888")
    
    earliest_total = float(earliest_vals[metric_col].sum())
    latest_total = float(latest_vals[metric_col].sum())
    
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
        delta_fmt = f"{int(delta_val):+d}" if not (is_percent or is_avg_metric) else f"{delta_val:+.1f}"
        delta_str = f"{delta_fmt}{'%' if is_percent else ''}"
        
        is_good = (delta_val < 0) if not higher_is_better else (delta_val > 0)
        color = "#1db954" if is_good else "#e91429"
    
    return val_str, delta_str, color

def get_metric_stats(df, metric_col, is_percent=False, higher_is_better=True):
    if df.empty or metric_col not in df.columns or 'date' not in df.columns:
        return ("0.0%" if is_percent else "0", None, "#888888")
    df_sorted = df.sort_values('date')
    grouped = df_sorted.groupby('project_key', sort=False, observed=True)
    return compute_metric_stats(grouped.first(), grouped.last(), grouped.ngroups, metric_col, is_percent=is_percent, higher_is_better=higher_is_better)

def render_login_page(auth_url: str):
    """Renders a visually prominent login screen in the main content area."""
    # Use columns to center the login card
    _, col2, _ = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # Main login card container
        st.markdown("""
            <div style="
                background-color: var(--card-bg, #181B22);
                border: 1px solid var(--card-border, rgba(255, 255, 255, 0.1));
                border-radius: 16px;
                padding: 3rem;
                text-align: center;
                box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            ">
                <div style="margin-bottom: 2rem;">
                    <i class="iconoir-fingerprint" style="font-size: 5rem; color: #3B82F6; filter: drop-shadow(0 0 15px rgba(59, 130, 246, 0.4));"></i>
                </div>
                <h2 style="margin-bottom: 1rem; font-weight: 700;">Access Restricted</h2>
                <p style="color: var(--text-muted, #888); margin-bottom: 2.5rem; font-size: 1.1rem;">
                    Authentication is required to access the enterprise SonarCloud metrics dashboard. 
                    Please sign in with your corporate Entra ID account.
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # Streamlit button needs to be outside the raw HTML string but visually attached
        st.link_button(
            "Login with Corporate AD", 
            url=auth_url, 
            type="primary", 
            use_container_width=True,
            icon=":material/login:"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("🔒 Secured by Microsoft Entra ID (formerly Azure AD)")

def display_dashboard(df, selected_projects, all_projects, branch_filter=None):
    """Display the main dashboard with metrics and charts"""
    
    project_names = {p['key']: p['name'] for p in all_projects}
    df['project_name'] = df['project_key'].map(project_names)
    
    # ⚡ Bolt Optimization: Sort dataframe by date once globally instead of multiple times
    # sorting in compute_metric_stats to prevent O(M*N log N) sorting bottleneck.
    if not df.empty and 'date' in df.columns:
        df_sorted = df.sort_values('date')
    else:
        df_sorted = df

    # ⚡ Bolt Optimization: Group the dataframe once globally to extract earliest and latest values
    # for all metrics simultaneously. This prevents computing 5 separate O(N) groupby operations
    # sequentially on the main thread, cutting the overhead by 80%.
    if not df_sorted.empty and 'project_key' in df_sorted.columns:
        grouped = df_sorted.groupby('project_key', sort=False, observed=True)
        earliest_vals = grouped.first()
        latest_vals = grouped.last()
        project_count = grouped.ngroups
    else:
        earliest_vals = pd.DataFrame()
        latest_vals = pd.DataFrame()
        project_count = 0

    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-graph-up"></i> Overview</h2>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        val, delta, color = compute_metric_stats(earliest_vals, latest_vals, project_count, 'vulnerabilities')
        create_metric_card("Vulnerabilities", val, "iconoir-bug", delta, color, neon_class="neon-green")
    
    with col2:
        val, delta, color = compute_metric_stats(earliest_vals, latest_vals, project_count, 'security_hotspots')
        create_metric_card("Security Hotspots", val, "iconoir-fire-flame", delta, color, neon_class="neon-orange")
    
    with col3:
        val, delta, color = compute_metric_stats(earliest_vals, latest_vals, project_count, 'duplicated_lines_density', is_percent=True)
        create_metric_card("Duplicated Lines", val, "iconoir-page", delta, color, neon_class="neon-teal")
    
    with col4:
        val, delta, color = compute_metric_stats(earliest_vals, latest_vals, project_count, 'security_rating')
        create_metric_card("Security Rating", val, "iconoir-lock", delta, color, neon_class="neon-green")
    
    with col5:
        val, delta, color = compute_metric_stats(earliest_vals, latest_vals, project_count, 'reliability_rating')
        create_metric_card("Reliability Rating", val, "iconoir-flash", delta, color, neon_class="neon-blue")
    
    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-graph-up"></i> Detailed Metrics</h2>', unsafe_allow_html=True)
    
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
    
    for preset in METRIC_PRESETS:
        METRIC_PRESETS[preset] = [m for m in METRIC_PRESETS[preset] if m in available_metrics]

    if "active_metrics" not in st.session_state:
        st.session_state.active_metrics = METRIC_PRESETS["Security Posture"]

    if "active_preset" not in st.session_state:
        st.session_state.active_preset = "Security Posture"

    def sync_preset_to_multiselect():
        selected_preset = st.session_state.preset_selector
        if not selected_preset:
            selected_preset = "Custom (Manual Selection)"
            st.session_state.preset_selector = selected_preset

        if selected_preset != "Custom (Manual Selection)":
            st.session_state.active_metrics = METRIC_PRESETS.get(selected_preset, [])
        st.session_state.active_preset = selected_preset

    def sync_multiselect_to_preset():
        current_metrics = set(st.session_state.metric_selector)
        matched_preset = "Custom (Manual Selection)"
        for preset_name, preset_metrics in METRIC_PRESETS.items():
            if preset_metrics and current_metrics == set(preset_metrics):
                matched_preset = preset_name
                break
        st.session_state.active_preset = matched_preset
        st.session_state.active_metrics = st.session_state.metric_selector

    st.pills(
        "Select a specific metric group:", 
        options=list(METRIC_PRESETS.keys()),
        selection_mode="single",
        key="preset_selector",
        default=st.session_state.active_preset,
        on_change=sync_preset_to_multiselect,
        help="Quickly switch between pre-configured metric combinations for analysis."
    )
    
    col1, col2 = st.columns([2, 1])

    with col1:
        # ⚡ Bolt Optimization: Pre-compute dictionary mapping for O(1) lookups in format_func
        # This prevents repeatedly executing .replace() and .title() on every render loop
        metric_display_names = {m: m.replace('_', ' ').title() for m in available_metrics}

        st.multiselect(
            "Or customize up to 3 individual metrics:",
            available_metrics,
            key="metric_selector",
            max_selections=3,
            default=st.session_state.active_metrics,
            format_func=lambda m: metric_display_names.get(m, m),
            on_change=sync_multiselect_to_preset,
            placeholder="Choose metrics to analyze...",
            help="Limiting selections ensures the trend charts remain readable without excessive scrolling."
        )

    def get_valid_chart_types(num_projects: int, num_metrics: int) -> list[str]:
        valid_charts = ["Line Chart"]
        if num_projects > 1 and num_metrics == 1:
            valid_charts.append("Bar Chart (Grouped)")
        if num_projects == 1 and num_metrics <= 2:
            valid_charts.append("Area Chart")
        return valid_charts

    with col2:
        active_project_count = len(selected_projects) if isinstance(selected_projects, list) else 1
        active_metric_count = len(st.session_state.get('metric_selector', []))
        allowed_charts = get_valid_chart_types(active_project_count, active_metric_count)
        chart_type = st.selectbox(
            "Chart type",
            options=allowed_charts,
            help="Chart options dynamically update based on the number of projects and metrics selected to ensure data is visually readable."
        )

    confirmed_metrics = st.session_state.get('metric_selector', [])
    
    if not confirmed_metrics:
        st.info("Please select at least one metric to render the trend analysis.", icon="📊")
        
    if not df.empty and confirmed_metrics:
        fig = None
        if chart_type in ["Line Chart", "Bar Chart (Grouped)"]:
            plot_type = "Line Chart" if chart_type == "Line Chart" else "Bar Chart"
            fig = render_dynamic_subplots(df, confirmed_metrics, project_names, chart_type=plot_type)
        elif chart_type == "Area Chart":
            fig = render_area_chart(df, date_col='date', metrics=confirmed_metrics)
            
        if fig:
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
    
    st.markdown('<h2 style="display: flex; align-items: center; gap: 0.5rem;"><i class="iconoir-list"></i> Metric Details</h2>', unsafe_allow_html=True)
    
    if not df.empty:
        display_data = df.copy()
        display_data['project_name'] = display_data['project_key'].map(project_names)
        
        if 'branch' in display_data.columns:
            display_data['branch'] = display_data['branch'].astype(object).fillna("").astype(str)
        else:
            display_data['branch'] = branch_filter if branch_filter else ""

        display_columns = ['date', 'project_name', 'branch'] + [col for col in available_metrics if col in display_data.columns]
        display_data = display_data[display_columns]
        display_data = display_data.sort_values(['date', 'project_name', 'branch'])
        
        for col in display_data.columns:
            if col not in ['project_name', 'date', 'project_key', 'branch']:
                try:
                    if 'rating' in col:
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0)
                    elif 'coverage' in col or 'density' in col or 'security_hotspots_reviewed' in col:
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0.0).round(2)
                    else:
                        display_data[col] = pd.to_numeric(display_data[col], errors='coerce').fillna(0).astype(int)
                except Exception:
                    display_data[col] = display_data[col].astype(str)
        
        column_config = {
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", width="medium"),
            "project_name": st.column_config.TextColumn("Project", width="medium"),
            "branch": st.column_config.TextColumn("Branch", width="small"),
            "vulnerabilities": st.column_config.NumberColumn("Vulns", format="%d"),
            "bugs": st.column_config.NumberColumn("Bugs", format="%d"),
            "security_hotspots": st.column_config.NumberColumn("Hotspots", format="%d"),
            "code_smells": st.column_config.NumberColumn("Smells", format="%d"),
            "coverage": st.column_config.ProgressColumn("Coverage", format="%.1f%%", min_value=0, max_value=100),
            "duplicated_lines_density": st.column_config.ProgressColumn("Duplication", format="%.1f%%", min_value=0, max_value=100),
            "security_rating": st.column_config.NumberColumn("Sec Rating", format="%.1f"),
            "reliability_rating": st.column_config.NumberColumn("Rel Rating", format="%.1f"),
            "sqale_rating": st.column_config.NumberColumn("Maint Rating", format="%.1f"),
             "security_review_rating": st.column_config.NumberColumn("Rev Rating", format="%.1f")
        }

        st.dataframe(display_data, use_container_width=True, hide_index=True, column_config=column_config)
        
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
        st.info("No data available for the selected metric. Please try adjusting your filters.", icon="ℹ️")
        return
    
    plot_data = df.copy()
    plot_data['project_name'] = plot_data['project_key'].map(project_names)
    
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
