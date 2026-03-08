import unittest
from unittest.mock import patch, MagicMock
import src.dashboard.auth as auth

class TestAuthSecurity(unittest.TestCase):
    @patch('src.dashboard.auth.get_msal_client')
    @patch('src.dashboard.auth.os.environ.get')
    def test_get_auth_url_includes_state(self, mock_env_get, mock_get_client):
        # Setup mocks
        mock_env_get.return_value = "http://localhost/redirect"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Call with state
        auth.get_auth_url(state="test_state_token")

        # Verify state was passed to MSAL
        mock_client.get_authorization_request_url.assert_called_once()
        call_kwargs = mock_client.get_authorization_request_url.call_args.kwargs
        self.assertIn("state", call_kwargs)
        self.assertEqual(call_kwargs["state"], "test_state_token")

    def test_logout_clears_auth_state(self):
        # Setup mock cookies
        mock_cookies = MagicMock()
        mock_cookies.__contains__.side_effect = lambda k: True

        # Call logout
        with patch('src.dashboard.auth.st') as _mock_st:
            auth.logout(cookies=mock_cookies)

        # Verify auth_state was deleted
        mock_cookies.__delitem__.assert_any_call("auth_state")
        mock_cookies.save.assert_called_once()

if __name__ == '__main__':
    unittest.main()
