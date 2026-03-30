import pytest
import os
import streamlit as st
from unittest.mock import patch, MagicMock

# Import the module to test
from data_service import get_secret, fetch_projects, fetch_project_branches, fetch_metrics_data

def test_get_secret_from_env():
    with patch.dict(os.environ, {"SONARCLOUD_API_TOKEN": "env-token"}):
        token = get_secret("sonarcloud", "api_token")
        assert token == "env-token"

def test_get_secret_from_streamlit_secrets(mock_st_secrets):
    with patch.dict(os.environ, {}, clear=True):
        token = get_secret("sonarcloud", "api_token")
        assert token == "fake-sonar-token"

@patch("data_service.st.error")
@patch("data_service.st.stop")
def test_get_secret_missing(mock_stop, mock_error):
    with patch.dict(os.environ, {}, clear=True):
        with patch("streamlit.secrets", {}):
            token = get_secret("sonarcloud", "nonexistent_key")
            assert token == ""
            mock_error.assert_called_once()
            mock_stop.assert_called_once()

def test_fetch_projects_success(mock_sonarcloud_api):
    st.cache_data.clear()
    projects = fetch_projects(mock_sonarcloud_api, "my-org")
    assert len(projects) == 2
    assert projects[0]["key"] == "proj1"
    mock_sonarcloud_api.get_organization_projects.assert_called_with("my-org")

@patch("data_service.st.error")
def test_fetch_projects_error(mock_error):
    st.cache_data.clear()
    api = MagicMock()
    api.get_organization_projects.side_effect = Exception("API failure")
    projects = fetch_projects(api, "my-org")
    assert projects == []
    mock_error.assert_called_once()

def test_fetch_project_branches_success(mock_sonarcloud_api):
    st.cache_data.clear()
    branches = fetch_project_branches(mock_sonarcloud_api, "proj1")
    assert len(branches) == 2
    assert branches[0]["name"] == "main"
    mock_sonarcloud_api.get_project_branches.assert_called_with("proj1")

@patch("data_service.st.warning")
def test_fetch_project_branches_error(mock_warning):
    st.cache_data.clear()
    api = MagicMock()
    api.get_project_branches.side_effect = Exception("API failure")
    branches = fetch_project_branches(api, "proj1")
    assert branches == []
    mock_warning.assert_called_once()

@patch("data_service.get_secret")
@patch("data_service._fetch_all_projects_history")
@patch("data_service.asyncio.run")
def test_fetch_metrics_data_fresh(mock_asyncio_run, mock_fetch_history, mock_get_secret, mock_sonarcloud_api, mock_storage_client):
    st.cache_data.clear()
    mock_get_secret.return_value = "fake-token"
    # Mock asyncio.run to just return a dummy result
    mock_asyncio_run.return_value = {
        "proj1": [
            {"date": "2023-10-01", "project_key": "proj1", "branch": "main", "coverage": 80.0, "bugs": 5}
        ]
    }
    
    # Needs to return dummy parquet bytes from compress_to_parquet
    with patch("data_service.compress_to_parquet") as mock_compress:
        mock_compress.return_value = b"fake-parquet-bytes"
        
        result = fetch_metrics_data(mock_sonarcloud_api, ["proj1"], 30, "main", _storage=mock_storage_client)
        assert result == b"fake-parquet-bytes"
        mock_storage_client.check_data_coverage.assert_called_with("proj1", "main", 30)
        mock_storage_client.store_metrics_data.assert_called()
        mock_compress.assert_called_once()

@patch("data_service.compress_to_parquet")
def test_fetch_metrics_data_cached(mock_compress, mock_sonarcloud_api, mock_storage_client):
    st.cache_data.clear()
    import pandas as pd
    # Ensure it uses cached data
    mock_storage_client.check_data_coverage.return_value = {
        "has_coverage": True,
        "latest_date": "2023-10-01",
        "data": pd.DataFrame([{"date": "2023-10-01", "project_key": "proj1", "coverage": 90.0, "bugs": 1}])
    }
    mock_compress.return_value = b"cached-parquet-bytes"
    
    result = fetch_metrics_data(mock_sonarcloud_api, ["proj1"], 30, "main", _storage=mock_storage_client)
    assert result == b"cached-parquet-bytes"
    # It shouldn't store anything new if it had full coverage
    mock_storage_client.store_metrics_data.assert_not_called()
