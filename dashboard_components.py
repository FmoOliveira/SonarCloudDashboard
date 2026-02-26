import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import io
from datetime import datetime

# Spotify-inspired Color Palette
CHART_COLORS = ['#1ed760', '#ffc862', '#2d46b9', '#b49bc8', '#1db954']
BG_COLOR = 'rgba(0,0,0,0)'  # Transparent
FONT_COLOR = '#ffffff'
GRID_COLOR = 'rgba(255,255,255,0.08)'

def apply_modern_layout(fig):
    """Apply modern transparent glassmorphism layout to Plotly figures"""
    fig.update_layout(
        autosize=True,
        plot_bgcolor=BG_COLOR,
        paper_bgcolor=BG_COLOR,
        font=dict(color=FONT_COLOR, family="Inter, sans-serif"),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(
            bgcolor='rgba(20, 30, 52, 0.5)',
            bordercolor='rgba(255, 255, 255, 0.1)',
            borderwidth=1
        ),
        hoverlabel=dict(
            bgcolor="rgba(10, 15, 28, 0.9)",
            font_size=13,
            font_family="Inter, sans-serif",
            bordercolor="rgba(0, 210, 255, 0.3)"
        )
    )
    
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=GRID_COLOR,
        zeroline=False,
        showline=False
    )
    
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=GRID_COLOR,
        zeroline=False,
        showline=False
    )
    return fig

def create_metric_card(title: str, value: str, icon_class: str):
    """Create a metric card with title, value, and Iconoir icon"""
    html = f"""
    <div style="
        background-color: #121212;
        border: 1px solid #7c7c7c;
        border-radius: 0.3rem;
        padding: 1.2rem;
        margin-bottom: 1rem;
    ">
        <div style="color: #ffffff; font-size: 0.95rem; font-weight: 500; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            <i class="{icon_class}" style="font-size: 1.2rem; color: #16a34a;"></i>
            <span>{title}</span>
        </div>
        <div style="color: #ffffff; font-size: 2rem; font-weight: bold;">
            {value}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

from plotly.subplots import make_subplots

def render_dynamic_subplots(df: pd.DataFrame, metrics: list, project_names: dict, chart_type: str = "Line Chart"):
    """
    Renders stacked subplots with synchronized X-axes to handle varying scales.
    Dynamically scales height based on the number of metrics.
    """
    if df.empty or not metrics:
        st.warning("No data available for the selected metrics.")
        return
        
    num_metrics = len(metrics)
    
    # Base height per subplot (in pixels)
    BASE_ROW_HEIGHT = 220 
    # Account for the global title, legend, and top/bottom margins
    CHART_CHROME_PADDING = 100 
    
    # Calculate total figure height
    total_height = (num_metrics * BASE_ROW_HEIGHT) + CHART_CHROME_PADDING

    fig = make_subplots(
        rows=num_metrics, 
        cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.08, # Provide breathing room between the X-axis and the next title
        subplot_titles=[m.replace('_', ' ').title() for m in metrics]
    )
    
    # Prepare data for plotting
    plot_data = df.copy()
    plot_data['project_name'] = plot_data['project_key'].map(project_names)
    
    # Convert date column if it exists
    if 'date' in plot_data.columns:
        try:
            plot_data['date'] = pd.to_datetime(plot_data['date'], format='mixed', errors='coerce', utc=True)
            plot_data['date'] = plot_data['date'].dt.tz_convert(None)
            plot_data = plot_data.sort_values('date')
        except Exception as e:
            st.warning(f"Could not parse dates: {str(e)}")
            return
    else:
        st.warning("No date information available for trend analysis.")
        return

    from datetime import timedelta
    
    # Dynamic Axis Bounds Calculation
    if not plot_data.empty and len(plot_data['date'].unique()) > 1:
        time_delta = plot_data['date'].max() - plot_data['date'].min()
        padding = time_delta * 0.05 if time_delta.days > 0 else timedelta(days=2)
        x_min = plot_data['date'].min() - padding
        x_max = plot_data['date'].max() + padding
        xaxis_range = [x_min, x_max]
        
        # Prevent intraday ticks (duplicate dates) on short timeframes
        dtick_val = 86400000.0 if time_delta.days <= 14 else None
    else:
        xaxis_range = None
        dtick_val = None

    projects = plot_data['project_name'].unique()
    
    for i, metric in enumerate(metrics):
        if metric in plot_data.columns:
            row_idx = i + 1 
            
            # Add a trace for each project
            for j, project in enumerate(projects):
                project_data = plot_data[plot_data['project_name'] == project]
                
                is_single_project = len(projects) == 1
                
                # If single project, color by metric and show metric in legend. 
                # If multiple projects, color by project and show project in legend (only on first subplot).
                if is_single_project:
                    trace_color = CHART_COLORS[i % len(CHART_COLORS)]
                    trace_name = metric.replace('_', ' ').title()
                    trace_legendgroup = metric
                    show_legend_for_trace = True # Show legend for each metric
                else:
                    trace_color = CHART_COLORS[j % len(CHART_COLORS)]
                    trace_name = project
                    trace_legendgroup = project
                    show_legend_for_trace = True if i == 0 else False
                
                if chart_type == "Bar Chart":
                    fig.add_trace(
                        go.Bar(
                            x=project_data['date'],
                            y=project_data[metric],
                            name=trace_name,
                            marker_color=trace_color,
                            legendgroup=trace_legendgroup,
                            showlegend=show_legend_for_trace,
                            width=1000 * 3600 * 20 # Force width to 20 hours (in milliseconds)
                        ),
                        row=row_idx, col=1
                    )
                else:
                    fig.add_trace(
                        go.Scatter(
                            x=project_data['date'],
                            y=project_data[metric],
                            mode='lines+markers',
                            name=trace_name,
                            connectgaps=True,  # Interpolates sparse missing scans
                            line=dict(shape='spline', smoothing=0.8, color=trace_color, width=3),
                            marker=dict(size=6, symbol='circle'),
                            legendgroup=trace_legendgroup,
                            showlegend=show_legend_for_trace
                        ),
                        row=row_idx, col=1
                    )
            
            # Dynamic Y-axis scaling per subplot
            y_title = "Percentage %" if "density" in metric or "coverage" in metric else "Count"
            fig.update_yaxes(title_text=y_title, row=row_idx, col=1, showgrid=True, gridcolor='#2D3748', zeroline=False)

    # Compute exact layout updates for every subplot X-axis to force Date continuity 
    # instead of categorical string fallbacks for Bar charts
    xaxis_updates = {}
    for i in range(1, num_metrics + 1):
        axis_key = f"xaxis{i}" if i > 1 else "xaxis"
        axis_dict = dict(
            type='date',
            range=xaxis_range,
            showgrid=False,
            zeroline=False,
            tickformat="%Y-%m-%d"
        )
        if dtick_val:
            axis_dict['dtick'] = dtick_val
            
        xaxis_updates[axis_key] = axis_dict

    fig.update_layout(
        height=total_height, # Inject the dynamically calculated height
        barmode='group' if chart_type == "Bar Chart" else None,
        margin=dict(l=20, r=20, t=60, b=20),
        **xaxis_updates,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        hovermode="x unified",
        legend=dict(
             orientation="h",
             yanchor="bottom",
             y=1.05,
             xanchor="center",
             x=0.5
        )
    )

    return fig

def create_comparison_chart(df: pd.DataFrame, metric: str, project_names: dict):
    """Create a bar chart comparing projects"""
    if df.empty or metric not in df.columns:
        st.warning("No data available for the selected metric.")
        return
    
    # Get latest data for each project
    latest_data = df.groupby('project_key')[metric].last().reset_index()
    latest_data['project_name'] = latest_data['project_key'].map(project_names)
    
    # Create bar chart
    fig = px.bar(
        latest_data,
        x='project_name',
        y=metric,
        title=f"{metric.replace('_', ' ').title()} by Project",
        color='project_name', # Color by project name to use custom palette
        color_discrete_sequence=CHART_COLORS
    )
    
    fig.update_layout(
        xaxis_title="",
        yaxis_title=metric.replace('_', ' ').title(),
        xaxis_tickangle=-45,
        showlegend=False
    )
    
    # Modern rounded bars
    fig.update_traces(marker_line_width=0, opacity=0.9)
    fig = apply_modern_layout(fig)
    
    st.plotly_chart(fig, use_container_width=True)

def render_area_chart(df: pd.DataFrame, date_col: str, metrics: list) -> go.Figure:
    """
    Renders an overlaid area chart optimized for dark mode visibility.
    """
    if df.empty or not metrics:
        st.warning("No data available for the selected metrics.")
        return
        
    fig = go.Figure()

    # Design Decision: Pre-calculate RGBA strings for high-contrast dark mode.
    # The line remains 100% opaque (alpha=1.0) for crisp boundaries, 
    # while the fill is dropped to 25% (alpha=0.25) to allow background traces to bleed through.
    color_palette = [
        ("rgba(49, 130, 206, 1.0)", "rgba(49, 130, 206, 0.25)"),   # Primary Blue
        ("rgba(72, 187, 120, 1.0)", "rgba(72, 187, 120, 0.25)"),   # Success Green
        ("rgba(237, 137, 54, 1.0)", "rgba(237, 137, 54, 0.25)")    # Warning Orange
    ]

    plot_data = df.copy()
    if date_col in plot_data.columns:
        try:
            plot_data[date_col] = pd.to_datetime(plot_data[date_col], format='mixed', errors='coerce', utc=True)
            plot_data[date_col] = plot_data[date_col].dt.tz_convert(None)
            plot_data = plot_data.sort_values(date_col)
        except Exception as e:
            st.warning(f"Could not parse dates: {str(e)}")
            return
            
    # Calculate global max values to order traces Z-index correctly (Largest in back, smallest in front)
    try:
        metrics.sort(key=lambda m: plot_data[m].max() if m in plot_data.columns else 0, reverse=True)
    except Exception:
        pass # fallback to default order

    for i, metric in enumerate(metrics):
        if metric in plot_data.columns:
            line_color, fill_color = color_palette[i % len(color_palette)]
            
            fig.add_trace(
                go.Scatter(
                    x=plot_data[date_col],
                    y=plot_data[metric],
                    mode='lines',
                    name=metric.replace('_', ' ').title(),
                    # spline smoothing maintains the modern aesthetic
                    line=dict(width=2, color=line_color, shape='spline', smoothing=0.8), 
                    fill='tozeroy',          # Fills the area down to the X-axis (Y=0)
                    fillcolor=fill_color,    # Applies the transparent 0.25 alpha color
                    connectgaps=True
                )
            )

    # Apply global theme overrides matching the config.toml secondary background
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode="x unified", # Essential UX: Shows the exact values of obscured traces
        yaxis=dict(
            showgrid=True,
            gridcolor='#2D3748', 
            zeroline=False
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            type='date',
            tickformat="%Y-%m-%d"
        ),
        margin=dict(l=10, r=10, t=40, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig

def create_rating_gauge(rating_value: float, title: str):
    """Create a gauge chart for rating metrics"""
    # SonarCloud ratings are typically 1-5 (1 being best, 5 being worst)
    colors = ['#00a650', '#85bb2f', '#ffcc00', '#ed9121', '#d4333f']
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = rating_value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title},
        gauge = {
            'axis': {'range': [None, 5]},
            'bar': {'color': colors[min(int(rating_value) - 1, 4)] if rating_value > 0 else colors[0]},
            'steps': [
                {'range': [0, 1], 'color': colors[0]},
                {'range': [1, 2], 'color': colors[1]},
                {'range': [2, 3], 'color': colors[2]},
                {'range': [3, 4], 'color': colors[3]},
                {'range': [4, 5], 'color': colors[4]}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 3
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor=BG_COLOR,
        font=dict(color=FONT_COLOR)
    )
    return fig

def create_coverage_donut(coverage_value: float):
    """Create a donut chart for coverage percentage"""
    remaining = 100 - coverage_value
    
    fig = go.Figure(data=[go.Pie(
        labels=['Covered', 'Not Covered'],
        values=[coverage_value, remaining],
        hole=.6,
        marker_colors=['#00a650', '#f0f0f0']
    )])
    
    fig.update_layout(
        title=dict(text="Test Coverage", font=dict(color=FONT_COLOR)),
        annotations=[dict(text=f'{coverage_value:.1f}%', x=0.5, y=0.5, font_size=20, showarrow=False, font=dict(color=FONT_COLOR))],
        height=300,
        showlegend=True,
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        legend=dict(font=dict(color=FONT_COLOR)),
        margin=dict(l=10, r=10, t=30, b=10)
    )
    
    return fig

def create_quality_gate_status(projects_data: pd.DataFrame):
    """Create a summary of quality gate status across projects"""
    if projects_data.empty:
        st.warning("No project data available.")
        return
    
    # Mock quality gate status based on metrics
    # In real implementation, you would fetch this from the SonarCloud API
    quality_gates = []
    
    for _, project in projects_data.iterrows():
        # Simple logic to determine quality gate status
        bugs = project.get('bugs', 0)
        vulnerabilities = project.get('vulnerabilities', 0)
        coverage = project.get('coverage', 0)
        
        if bugs == 0 and vulnerabilities == 0 and coverage >= 80:
            status = "Passed"
            color = "#00a650"
        elif bugs <= 5 and vulnerabilities <= 2 and coverage >= 60:
            status = "Warning"
            color = "#ffcc00"
        else:
            status = "Failed"
            color = "#d4333f"
        
        quality_gates.append({
            'project': project.get('project_key', 'Unknown'),
            'status': status,
            'color': color
        })
    
    # Create status summary
    status_counts = pd.DataFrame(quality_gates)['status'].value_counts()
    
    fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Quality Gate Status Distribution",
        color=status_counts.index,
        color_discrete_map={
            'Passed': '#00ff87',
            'Warning': '#ffcc00',
            'Failed': '#ff007c'
        }
    )
    
    fig = apply_modern_layout(fig)
    fig.update_traces(hole=.4, hoverinfo="label+percent+name")
    
    st.plotly_chart(fig, use_container_width=True)

def format_metric_value(metric: str, value):
    """Format metric values for display"""
    if pd.isna(value):
        return "N/A"
    
    if metric in ['coverage', 'duplicated_lines_density']:
        return f"{float(value):.1f}%"
    elif metric in ['bugs', 'vulnerabilities', 'security_hotspots', 'code_smells', 'violations']:
        return str(int(value))
    elif 'rating' in metric:
        rating_map = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E'}
        try:
            return rating_map.get(int(float(value)), str(value))
        except (ValueError, TypeError):
            return str(value)
    else:
        return str(value)

def create_metrics_heatmap(df: pd.DataFrame, project_names: dict):
    """Create a heatmap of metrics across projects"""
    if df.empty:
        st.warning("No data available for heatmap.")
        return
    
    # Get latest data for each project
    latest_data = df.groupby('project_key').last().reset_index()
    latest_data['project_name'] = latest_data['project_key'].map(project_names)
    
    # Select numeric metrics for heatmap
    numeric_metrics = ['coverage', 'duplicated_lines_density', 'bugs', 'vulnerabilities', 'code_smells']
    available_metrics = [m for m in numeric_metrics if m in latest_data.columns]
    
    if not available_metrics:
        st.warning("No numeric metrics available for heatmap.")
        return
    
    # Prepare data for heatmap
    heatmap_data = latest_data[['project_name'] + available_metrics].set_index('project_name')
    
    # Normalize data for better visualization
    normalized_data = heatmap_data.copy()
    for col in available_metrics:
        if col in ['coverage']:
            # Higher is better, no normalization needed
            pass
        else:
            # Lower is better, invert for visualization
            max_val = normalized_data[col].max()
            if max_val > 0:
                normalized_data[col] = max_val - normalized_data[col]
    
    fig = px.imshow(
        normalized_data.T,
        title="Project Metrics Heatmap",
        color_continuous_scale='RdYlGn',
        aspect='auto'
    )
    
    fig = apply_modern_layout(fig)
    
    st.plotly_chart(fig, use_container_width=True)

def inject_statistical_anomalies(
    fig: go.Figure, 
    df: pd.DataFrame, 
    date_col: str, 
    metrics: list, 
    window_size: int = 14, 
    z_threshold: float = 3.0
) -> go.Figure:
    """
    Scans the dataframe for statistically significant metric spikes using a rolling Z-score 
    and injects vertical warning lines into the Plotly figure.
    """
    df_sorted = df.sort_values(by=date_col).reset_index(drop=True)
    flagged_dates = set()

    for metric in metrics:
        if metric not in df_sorted.columns:
            continue
            
        # 1. Calculate Rolling Statistics
        # min_periods=1 ensures the mean calculates immediately, preventing cold starts
        rolling_mean = df_sorted[metric].rolling(window=window_size, min_periods=1).mean()
        
        # Standard deviation requires at least 2 points
        rolling_std = df_sorted[metric].rolling(window=window_size, min_periods=2).std()
        
        # 2. The Zero-Variance Edge Case (Architectural Key)
        # If a metric is perfectly stable (e.g., 0 vulnerabilities for a month), std is 0.
        # Division by zero yields NaN. We replace 0 and NaN with infinity to force 
        # the resulting Z-score to 0, preventing the pipeline from crashing.
        rolling_std = rolling_std.replace(0, np.nan).fillna(float('inf'))
        
        # 3. Vectorized Z-Score Calculation
        z_scores = (df_sorted[metric] - rolling_mean) / rolling_std
        
        # 4. Filter for positive anomalies (we only care about quality degradation)
        anomalies = df_sorted[(z_scores > z_threshold)]
        
        for idx, row in anomalies.iterrows():
            anomaly_date = row[date_col]
            
            if anomaly_date not in flagged_dates:
                # 5. Inject the UI Marker (Cast Timestamp to Unix milliseconds to prevent Plotly annotation TypeErrors)
                fig.add_vline(
                    x=anomaly_date.timestamp() * 1000,
                    line_width=2,
                    line_dash="dot",
                    line_color="rgba(229, 62, 62, 0.8)", # Warning red
                    annotation_text=f"🚨 Statistical Anomaly",
                    annotation_position="top right",
                    annotation_font=dict(size=10, color="#FCA5A5")
                )
                flagged_dates.add(anomaly_date)

    return fig

def compress_to_parquet(df: pd.DataFrame) -> bytes:
    """
    Serializes a Pandas DataFrame into a highly compressed Parquet byte array.
    """
    if df.empty:
        return b""
        
    buffer = io.BytesIO()
    
    # PyArrow is the C++ backend that makes this execution lightning fast
    df.to_parquet(buffer, engine='pyarrow', compression='snappy', index=False)
    
    return buffer.getvalue()

def decompress_from_parquet(parquet_bytes: bytes) -> pd.DataFrame:
    """
    Deserializes a Parquet byte array back into a Pandas DataFrame.
    """
    if not parquet_bytes:
        return pd.DataFrame()
        
    buffer = io.BytesIO(parquet_bytes)
    return pd.read_parquet(buffer, engine='pyarrow')
