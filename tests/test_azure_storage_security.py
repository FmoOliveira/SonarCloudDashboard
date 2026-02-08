import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from azure_storage import AzureTableStorage

class TestAzureStorageSecurity(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"

        # Mock TableServiceClient
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_retrieve_metrics_data_query_construction(self):
        """Test that retrieve_metrics_data constructs the query correctly using parameters"""
        project_key = "test_project"
        branch = "main' or PartitionKey eq 'hacked" # Injection attempt
        days = 30

        # Call the method
        self.storage.retrieve_metrics_data(project_key, branch, days)

        # Check the call arguments
        self.mock_table_client.query_entities.assert_called()
        call_args = self.mock_table_client.query_entities.call_args

        # Check query_filter
        query_filter = call_args.kwargs.get('query_filter')
        if not query_filter and len(call_args[0]) > 0:
            query_filter = call_args[0][0]

        print(f"Constructed Query: {query_filter}")

        # Assert that the query uses placeholders
        self.assertIn("@pk", query_filter)
        self.assertIn("@start_date", query_filter)
        self.assertNotIn(branch, query_filter) # The injected string should NOT be in the query string directly

        # Check parameters
        parameters = call_args.kwargs.get('parameters')
        self.assertIsNotNone(parameters)
        self.assertEqual(parameters['pk'], f"{project_key}_{branch}")

    def test_delete_project_data_query_construction(self):
        """Test that delete_project_data constructs the query correctly using parameters"""
        project_key = "test_project"
        branch = "main"

        self.storage.delete_project_data(project_key, branch)

        self.mock_table_client.query_entities.assert_called()
        call_args = self.mock_table_client.query_entities.call_args

        query_filter = call_args.kwargs.get('query_filter')
        if not query_filter and len(call_args[0]) > 0:
            query_filter = call_args[0][0]

        print(f"Delete Query: {query_filter}")

        # Assert placeholders
        self.assertIn("@pk", query_filter)

        # Check parameters
        parameters = call_args.kwargs.get('parameters')
        self.assertIsNotNone(parameters)
        self.assertEqual(parameters['pk'], f"{project_key}_{branch}")

if __name__ == '__main__':
    unittest.main()
