import unittest
from unittest.mock import MagicMock, patch
# Import the module to patch the constant later
import azure_storage
from azure_storage import AzureTableStorage

class TestResourceLimits(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    @patch('azure_storage.MAX_RETRIEVAL_LIMIT', 10, create=True)
    @patch('streamlit.warning')
    def test_retrieve_metrics_limit(self, mock_warning):
        """Test that retrieve_metrics_data stops after limit"""
        # Create an iterator with 20 items
        items = [{'PartitionKey': 'pk', 'RowKey': str(i), 'val': i} for i in range(20)]
        self.mock_table_client.query_entities.return_value = iter(items)

        results = self.storage.retrieve_metrics_data('project_key')

        # Verify result length matches the limit
        self.assertEqual(len(results), 10)

        # Verify warning was called with appropriate message
        found_limit_warning = False
        for call in mock_warning.call_args_list:
            if "limit" in call[0][0] and "truncated" in call[0][0]:
                found_limit_warning = True
                break
        self.assertTrue(found_limit_warning, "Did not warn about truncated results")

    @patch('azure_storage.MAX_RETRIEVAL_LIMIT', 10, create=True)
    @patch('streamlit.warning')
    def test_get_stored_projects_limit(self, mock_warning):
        """Test that get_stored_projects stops after limit (slow path)"""
        # Ensure fast path is skipped (missing metadata)
        # The code catches Exception when getting MIGRATION_STATUS
        self.mock_table_client.get_entity.side_effect = Exception("Not found")

        # Create an iterator with 20 items
        items = [{'ProjectKey': f'proj_{i}'} for i in range(20)]
        self.mock_table_client.list_entities.return_value = iter(items)

        projects = self.storage.get_stored_projects()

        # Verify result length matches the limit
        self.assertEqual(len(projects), 10)

        # Verify warning was called with appropriate message
        found_limit_warning = False
        for call in mock_warning.call_args_list:
            if "limit" in call[0][0] and "incomplete" in call[0][0]:
                found_limit_warning = True
                break
        self.assertTrue(found_limit_warning, "Did not warn about incomplete project list")
