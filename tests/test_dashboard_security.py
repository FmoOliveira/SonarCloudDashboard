import unittest
from dashboard_components import create_metric_card
import streamlit as st
from unittest.mock import patch, MagicMock

class TestDashboardSecurity(unittest.TestCase):
    def test_metric_card_xss_prevention(self):
        """Test that create_metric_card escapes HTML in title and value"""

        # Malicious inputs
        malicious_title = "<script>alert('XSS')</script>Title"
        malicious_value = "<img src=x onerror=alert(1)>100"
        malicious_icon = '"><script>alert(1)</script><i class="'

        # Mock st.markdown to capture the output
        with patch('streamlit.markdown') as mock_markdown:
            create_metric_card(malicious_title, malicious_value, malicious_icon)

            # Get the argument passed to st.markdown
            args, _ = mock_markdown.call_args
            html_output = args[0]

            # Assert that the malicious scripts are NOT present in their executable form
            self.assertNotIn("<script>", html_output)
            self.assertNotIn("<img", html_output)

            # Assert that they ARE present in escaped form
            self.assertIn("&lt;script&gt;", html_output)
            self.assertIn("&lt;img", html_output)
