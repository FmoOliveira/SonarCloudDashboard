import pytest
import os
from unittest.mock import patch, MagicMock
from auth import get_auth_url, acquire_token_by_auth_code, logout

@patch("auth.get_msal_client")
def test_get_auth_url(mock_get_client, mock_st_secrets):
    mock_client = MagicMock()
    mock_client.get_authorization_request_url.return_value = "https://login.microsoftonline.com/auth"
    mock_get_client.return_value = mock_client
    
    with patch.dict(os.environ, {}, clear=True):
        url = get_auth_url(state="mock-state")
        assert url == "https://login.microsoftonline.com/auth"
        mock_client.get_authorization_request_url.assert_called_once_with(
            ["User.Read"],
            redirect_uri="http://localhost:8501",
            state="mock-state"
        )

@patch("auth.get_msal_client")
def test_acquire_token_by_auth_code(mock_get_client, mock_st_secrets):
    mock_client = MagicMock()
    mock_client.acquire_token_by_authorization_code.return_value = {"access_token": "mock-token"}
    mock_get_client.return_value = mock_client
    
    with patch.dict(os.environ, {}, clear=True):
        result = acquire_token_by_auth_code("mock-code")
        assert result == {"access_token": "mock-token"}
        mock_client.acquire_token_by_authorization_code.assert_called_once_with(
            "mock-code",
            scopes=["User.Read"],
            redirect_uri="http://localhost:8501"
        )

@patch("auth.st.rerun")
@patch("auth.st.info")
def test_logout(mock_info, mock_rerun):
    mock_cookies = MagicMock()
    mock_cookies.__contains__.side_effect = lambda k: k in ["auth_token", "user_info_name"]
    
    logout(cookies=mock_cookies)
    mock_cookies.__delitem__.assert_any_call("auth_token")
    mock_cookies.__delitem__.assert_any_call("user_info_name")
    mock_cookies.save.assert_called_once()
    mock_info.assert_called_once()
    mock_rerun.assert_called_once()
