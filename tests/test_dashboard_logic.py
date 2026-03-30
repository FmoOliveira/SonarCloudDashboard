import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/dashboard'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/dashboard/database'))

import pytest
import pandas as pd
from dashboard_view import compute_metric_stats

def test_compute_metric_stats_sum():
    earliest_vals = pd.DataFrame({'bugs': [10, 5], 'project_key': ['A', 'B']})
    latest_vals = pd.DataFrame({'bugs': [12, 6], 'project_key': ['A', 'B']})

    val_str, delta_str, color = compute_metric_stats(earliest_vals, latest_vals, 2, 'bugs', is_percent=False, higher_is_better=False)

    assert val_str == "18"
    assert delta_str == "+3"
    assert color == "#e91429" # Bad because bugs went up

def test_compute_metric_stats_avg():
    earliest_vals = pd.DataFrame({'coverage': [80.0, 90.0], 'project_key': ['A', 'B']})
    latest_vals = pd.DataFrame({'coverage': [85.0, 95.0], 'project_key': ['A', 'B']})

    val_str, delta_str, color = compute_metric_stats(earliest_vals, latest_vals, 2, 'coverage', is_percent=True, higher_is_better=True)

    assert val_str == "90.0%"
    assert delta_str == "+5.0%"
    assert color == "#1db954" # Good because coverage went up

def test_compute_metric_stats_empty():
    earliest_vals = pd.DataFrame()
    latest_vals = pd.DataFrame()

    val_str, delta_str, color = compute_metric_stats(earliest_vals, latest_vals, 0, 'bugs', is_percent=False)

    assert val_str == "0"
    assert delta_str is None
    assert color == "#888888"
