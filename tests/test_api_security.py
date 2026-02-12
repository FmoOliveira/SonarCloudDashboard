import unittest
from unittest.mock import MagicMock, patch
from sonarcloud_api import SonarCloudAPI

class TestAPISecurity(unittest.TestCase):
    def test_request_timeout(self):
        """Test that API requests include a timeout"""
        api = SonarCloudAPI("test_token")

        with patch.object(api.session, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {}

            # Call a method that triggers a request
            api.get_organization_projects("test_org")

            # Verify timeout was passed
            mock_get.assert_called()
            call_kwargs = mock_get.call_args.kwargs
            self.assertIn('timeout', call_kwargs, "Timeout parameter missing in API request")
            self.assertEqual(call_kwargs['timeout'], 30, "Timeout should be set to 30 seconds")

if __name__ == '__main__':
    unittest.main()
