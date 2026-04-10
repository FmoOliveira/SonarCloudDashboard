import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from auth_manager import get_login_url, do_logout, handle_auth

class MockCookies(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save = MagicMock()
        self.ready = MagicMock(return_value=True)

def test_get_login_url(mock_config):
    """Test that get_login_url correctly interacts with cookies and MSAL."""
    mock_cookies = MockCookies()
    
    with patch("auth_manager.get_msal_client") as mock_get_client:
        mock_client = mock_get_client.return_value
        mock_client.get_authorization_request_url.return_value = "https://login.microsoftonline.com/auth"
        
        url = get_login_url(mock_cookies)
        
        assert url == "https://login.microsoftonline.com/auth"
        # Verify state was set in cookies
        assert "auth_state" in mock_cookies
        # Verify MSAL client was used
        mock_client.get_authorization_request_url.assert_called_once()

def test_do_logout(mock_config):
    """Test that do_logout clears session state and cookies."""
    mock_cookies = MockCookies({"auth_token": "some-token"})
    
    with patch("auth_manager.st") as mock_st:
        # Mock session_state as a dict for easier access
        mock_st.session_state = {}
        do_logout(mock_cookies)
        
        # Verify cookie cleared (either set to None or popped)
        # auth_manager.py calls cookies.pop("auth_token", None)
        assert "auth_token" not in mock_cookies or mock_cookies.get("auth_token") is None
        # Verify session state markers
        assert mock_st.session_state["pending_logout"] is True
        mock_st.rerun.assert_called_once()

@patch("auth_manager.get_msal_client")
@patch("auth_manager.st")
def test_handle_auth_callback_success(mock_st, mock_get_client, mock_config):
    """Test the OAuth callback processing in handle_auth."""
    mock_cookies = MockCookies({"auth_state": "expected-state"})
    
    # Simulate query params return from OIDC
    mock_st.query_params = {
        "code": "auth-code-123",
        "state": "expected-state"
    }
    mock_st.session_state = {}
    
    mock_client = mock_get_client.return_value
    mock_client.acquire_token_by_authorization_code.return_value = {
        "access_token": "valid-access-token",
        "id_token_claims": {"name": "Test User"}
    }
    
    # We need to mock encrypt_val to return something predictable
    with patch("auth_manager.encrypt_val", side_effect=lambda x: f"enc_{x}"):
        with patch("auth_manager._get_user_photo", return_value=None):
            token = handle_auth(mock_cookies)
            
            assert token == "valid-access-token"
            assert mock_cookies["auth_token"] == "enc_valid-access-token"
            assert mock_cookies["user_info_name"] == "enc_Test User"
            # Verify query params were cleared
            # mock_st.query_params is a dict, so clear() works. 
            # We check if it's empty now.
            assert len(mock_st.query_params) == 0
