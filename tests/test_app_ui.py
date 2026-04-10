import pytest
from streamlit.testing.v1 import AppTest
from unittest.mock import patch
import os

def test_unauthenticated_view():
    """Verify that unauthenticated users are directed to the login page."""
    # Force DEMO_MODE off to see login screen
    with patch.dict(os.environ, {"DEMO_MODE": "0"}):
        with patch("streamlit.secrets", {
            "sonarcloud": {"api_token": "fake", "organization_key": "fake"},
            "azure_ad": {"tenant_id": "fake", "client_id": "fake", "client_secret": "fake", "redirect_uri": "http://localhost:8501"},
            "cookie_encryption_key": "fake-key-with-at-least-32-chars-!!!!"
        }):
            # Need to mock MSAL to avoid OIDC discovery network requests
            with patch("msal.ConfidentialClientApplication") as mock_msal:
                mock_msal.return_value.get_authorization_request_url.return_value = "http://fake-auth-url"
                
                # Use local vendored cookie manager mock target
                with patch("streamlit_cookies_manager_local.CookieManager") as mock_cookie_manager:
                    mock_cookies = mock_cookie_manager.return_value
                    mock_cookies.ready.return_value = True
                    mock_cookies.get.return_value = None
                    mock_cookies.__contains__.return_value = False

                    at = AppTest.from_file("src/dashboard/app.py")
                    # Increase timeout to handle multiple reruns if any
                    at.run(timeout=10)
                
                assert not at.exception
                # Check for "Access Restricted" text in markdown
                assert any("Access Restricted" in str(m.value) for m in at.markdown)

def test_demo_mode_view():
    """Verify that DEMO_MODE=1 bypasses auth and displays the dashboard with dummy data."""
    with patch.dict(os.environ, {"DEMO_MODE": "1"}, clear=True):
        with patch("streamlit_cookies_manager_local.CookieManager") as mock_cookie_manager:
            mock_cookies = mock_cookie_manager.return_value
            mock_cookies.ready.return_value = True
            mock_cookies.get.return_value = None
            
            at = AppTest.from_file("src/dashboard/app.py")
            at.run(timeout=10)
            
            assert not at.exception
            # In demo mode, "Demo User" should be in the sidebar popover label or initials
            # Since AppTest's support for popovers/sidebar nested elements varies, 
            # we check common text locations.
            sidebar_text = " ".join(str(m.value) for m in at.sidebar.markdown)
            main_text = " ".join(str(m.value) for m in at.markdown)
            all_text = sidebar_text + " " + main_text
            
            assert "Demo User" in all_text or "DU" in all_text
            
            # Sidebar should load demo projects
            assert len(at.sidebar.selectbox) >= 1
