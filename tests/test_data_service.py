import pytest
import os
import streamlit as st
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock
from sonarcloud_api import SonarCloudAPI

# Import the module to test
from data_service import fetch_projects, fetch_project_branches, fetch_metrics_data, DataServiceError

def test_fetch_projects_success(mock_config):
    """Test that fetch_projects correctly initializes the API and returns projects."""
    st.cache_data.clear()
    
    with patch("data_service.config", mock_config):
        with patch("data_service.SonarCloudAPI") as mock_api_class:
            mock_api = mock_api_class.return_value
            mock_api.get_organization_projects = AsyncMock(return_value=[
                {"key": "proj1", "name": "Project 1"}
            ])
            
            projects = fetch_projects("my-org")
            
            assert len(projects) == 1
            assert projects[0]["key"] == "proj1"
            # Verify it used the secret token from config
            mock_api_class.assert_called_once()
            args, _ = mock_api_class.call_args
            assert args[0] == "fake-sonar-token"

@patch("data_service.logger.error")
def test_fetch_projects_error(mock_log_error, mock_config):
    """Test that fetch_projects handles API errors gracefully."""
    st.cache_data.clear()
    
    with patch("data_service.SonarCloudAPI") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_organization_projects.side_effect = Exception("API failure")
        
        with pytest.raises(DataServiceError):
            fetch_projects("my-org")
        
        # Verify error was logged correctly
        assert mock_log_error.called

def test_fetch_project_branches_success(mock_config):
    """Test that fetch_project_branches correctly handles branch retrieval."""
    st.cache_data.clear()
    
    with patch("data_service.SonarCloudAPI") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_project_branches = AsyncMock(return_value=[
            {"name": "main", "isMain": True}
        ])
        
        branches = fetch_project_branches("proj1")
        assert len(branches) == 1
        assert branches[0]["name"] == "main"

@patch("data_service.run_async")
@patch("data_service.compress_to_parquet")
def test_fetch_metrics_data_fresh(mock_compress, mock_run_async, mock_config, mock_storage_client):
    """Test fetch_metrics_data when it needs to fetch new data from SonarCloud."""
    st.cache_data.clear()
    
    # Mock storage to say 'no coverage'
    mock_storage_client.check_data_coverage.return_value = {
        "has_coverage": False,
        "latest_date": None,
        "data": None,
        "record_count": 0,
        "days_since_latest": None,
        "missing_metrics": []
    }
    
    # Mock data results
    mock_run_async.return_value = {
        "proj1": [{"date": "2023-10-01", "project_key": "proj1", "coverage": 80.0}]
    }
    mock_compress.return_value = b"parquet-bytes"
    
    result = fetch_metrics_data(["proj1"], 30, "main", _storage=mock_storage_client)
    
    assert result == b"parquet-bytes"
    mock_run_async.assert_called_once()
    mock_storage_client.store_metrics_data.assert_called_once()

@patch("data_service.compress_to_parquet")
def test_fetch_metrics_data_cached(mock_compress, mock_config, mock_storage_client):
    """Test fetch_metrics_data shortcut when database already has full coverage."""
    st.cache_data.clear()
    
    # Mock storage to say 'has coverage'
    mock_storage_client.check_data_coverage.return_value = {
        "has_coverage": True,
        "latest_date": "2023-10-01",
        "data": pd.DataFrame([{"date": "2023-10-01", "project_key": "proj1", "coverage": 90.0}]),
        "record_count": 1,
        "days_since_latest": 0,
        "missing_metrics": []
    }
    mock_compress.return_value = b"cached-bytes"
    
    result = fetch_metrics_data(["proj1"], 30, "main", _storage=mock_storage_client)
    
    assert result == b"cached-bytes"
    # Verify no storage writing happened
    mock_storage_client.store_metrics_data.assert_not_called()
