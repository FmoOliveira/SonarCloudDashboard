import pytest
import os
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_st_secrets():
    # Mock streamlit.secrets dictionary behaviour
    secrets = {
        "sonarcloud": {
            "api_token": "fake-sonar-token",
            "organization_key": "fake-org"
        },
        "azure_ad": {
            "tenant_id": "fake-tenant",
            "client_id": "fake-client-id",
            "client_secret": "fake-client-secret",
            "redirect_uri": "http://localhost:8501"
        }
    }
    with patch("streamlit.secrets", secrets):
        yield secrets

@pytest.fixture
def mock_env_vars():
    env_vars = {
        "SONARCLOUD_API_TOKEN": "env-sonar-token",
        "SONARCLOUD_ORGANIZATION_KEY": "env-org"
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars

@pytest.fixture
def mock_sonarcloud_api():
    api = MagicMock()
    api.get_organization_projects.return_value = [
        {"key": "proj1", "name": "Project 1"},
        {"key": "proj2", "name": "Project 2"}
    ]
    api.get_project_branches.return_value = [
        {"name": "main", "isMain": True},
        {"name": "develop", "isMain": False}
    ]
    api.get_project_measures.return_value = {"coverage": 85.5, "bugs": 2}
    return api

@pytest.fixture
def mock_storage_client():
    storage = MagicMock()
    # By default, say there's no coverage to force fresh fetch in testing,
    # or override in specific tests
    storage.check_data_coverage.return_value = {
        "has_coverage": False,
        "latest_date": None,
        "data": None
    }
    storage.store_metrics_data.return_value = True
    return storage
