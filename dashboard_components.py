import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
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
            borderwidth=1,
            borderpad=4
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
            <i class="{icon_class}" style="font-size: 1.2rem; color: #1ed760;"></i>
            <span>{title}</span>
        </div>
        <div style="color: #ffffff; font-size: 2rem; font-weight: bold;">
            {value}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def create_trend_chart(df: pd.DataFrame, metric: str, project_names: dict):
    """Create a line chart showing metric trends over time"""
    if df.empty or metric not in df.columns:
        st.warning("No data available for the selected metric.")
        return
    
    # Prepare data for plotting
    plot_data = df.copy()
    plot_data['project_name'] = plot_data['project_key'].map(project_names)
    
    # Convert date column if it exists
    if 'date' in plot_data.columns:
        try:
            # Handle different date formats from SonarCloud API
            plot_data['date'] = pd.to_datetime(plot_data['date'], format='mixed', errors='coerce', utc=True)
            # Convert to consistent timezone
            plot_data['date'] = plot_data['date'].dt.tz_convert(None)
            plot_data = plot_data.sort_values('date')
        except Exception as e:
            st.warning(f"Could not parse dates: {str(e)}")
            return
    else:
        st.warning("No date information available for trend analysis.")
        return
    
    # Create line chart
    fig = px.line(
        plot_data,
        x='date',
        y=metric,
        color='project_name',
        title=f"{metric.replace('_', ' ').title()} Trend Over Time",
        markers=True,
        color_discrete_sequence=CHART_COLORS
    )
    
    fig.update_layout(
        xaxis_title="",
        yaxis_title=metric.replace('_', ' ').title(),
        legend_title="Project"
    )
    
    # Apply soft glow to lines
    fig.update_traces(line=dict(width=3))
    
    fig = apply_modern_layout(fig)
    
    st.plotly_chart(fig, use_container_width=True)

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
