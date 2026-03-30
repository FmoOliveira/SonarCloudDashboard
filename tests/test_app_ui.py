import pytest
from streamlit.testing.v1 import AppTest
from unittest.mock import patch
import os

def test_unauthenticated_view():
    # Force DEMO_MODE off to see login screen
    with patch.dict(os.environ, {"DEMO_MODE": "0"}):
        # We also need to mock secrets in the app to avoid KeyError
        # Streamlit AppTest creates a simulated run
        with patch("streamlit.secrets", {
            "sonarcloud": {"api_token": "fake", "organization_key": "fake"},
            "azure_ad": {"tenant_id": "fake", "client_id": "fake", "client_secret": "fake", "redirect_uri": "http://localhost:8501"}
        }):
            # Need to mock MSAL to avoid OIDC discovery network requests
            with patch("msal.ConfidentialClientApplication") as mock_msal:
                mock_msal.return_value.get_authorization_request_url.return_value = "http://fake-auth-url"
                with patch("streamlit_cookies_manager.CookieManager") as mock_cookie_manager:
                    mock_cookies = mock_cookie_manager.return_value
                    mock_cookies.ready.return_value = True
                    mock_cookies.get.return_value = None
                    mock_cookies.__contains__.return_value = False

                    at = AppTest.from_file("src/dashboard/app.py")
                    at.run()
                
                assert not at.exception
                # Without auth, 'render_login_page' creates a link to login
                # Check for "Access Restricted" text in the markdown output
                assert any("Access Restricted" in str(item.value) for item in at.markdown if item.value)

def test_demo_mode_view():
    with patch.dict(os.environ, {"DEMO_MODE": "1"}, clear=True):
        with patch("streamlit_cookies_manager.CookieManager") as mock_cookie_manager:
            mock_cookies = mock_cookie_manager.return_value
            mock_cookies.ready.return_value = True
            mock_cookies.get.return_value = None
            
            at = AppTest.from_file("src/dashboard/app.py")
            at.run()
            
            assert not at.exception
            # In demo mode, it bypasses auth and shows Demo User
            assert any("Demo User" in str(item.value) for item in at.markdown if item.value)
            
            # Sidebar should load demo project. AppTest returns the mapped values if format_func is used
            assert len(at.sidebar.selectbox) >= 1
            project_box = at.sidebar.selectbox[0]
            assert "Frontend Web Application" in project_box.options
            
            # Simulate clicking "Load Dashboard" button inside the form
            if len(at.button) > 0:
                # Find the form submit button
                load_btn = [btn for btn in at.button if btn.label == "Load Dashboard"]
                if load_btn:
                    load_btn[0].set_value(True)
                    at.run()
                    assert not at.exception
                    assert any("No data found" in str(item.label) for item in at.status)
