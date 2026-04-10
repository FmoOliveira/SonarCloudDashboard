import pytest
from unittest.mock import patch, MagicMock
from auth_manager import get_login_url, handle_auth

class MockCookies(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save = MagicMock()
        self.ready = MagicMock(return_value=True)

def test_get_login_url_sets_csrf_state(mock_config):
    """Verify that every login URL generation associates a unique state token for CSRF protection."""
    mock_cookies = MockCookies()
    
    with patch("auth_manager.get_msal_client") as mock_get_client:
        get_login_url(mock_cookies)
        
        # auth_state should have been set in the cookie
        assert "auth_state" in mock_cookies
        assert len(mock_cookies["auth_state"]) >= 32 # Token length check

def test_handle_auth_prevents_csrf_mismatch(mock_config):
    """Verify that handle_auth rejects OAuth callbacks with mismatched state tokens."""
    mock_cookies = MockCookies({"auth_state": "correct-state"})
    
    with patch("auth_manager.st") as mock_st:
        mock_st.query_params = {
            "code": "any-code",
            "state": "TAMPERED-STATE"
        }
        mock_st.session_state = {}
        
        token = handle_auth(mock_cookies)
        
        assert token == ""
        # Should clear query params even on failure to avoid looping
        assert len(mock_st.query_params) == 0
        # Should show an error to user
        mock_st.error.assert_called_once()
