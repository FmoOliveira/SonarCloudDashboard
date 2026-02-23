import unittest
from unittest.mock import MagicMock, patch
from azure_storage import AzureTableStorage

class TestResourceLimits(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_retrieve_metrics_data_limit(self):
        """Test that retrieve_metrics_data does not fetch an unlimited number of records"""

        # Create a generator that yields a large number of items
        def massive_result_generator():
            for i in range(20000): # Simulate 20k records
                yield {
                    "PartitionKey": "pk",
                    "RowKey": f"rk_{i}",
                    "ProjectKey": "p",
                    "Branch": "b",
                    "Date": "2025-01-01",
                    "bugs": i
                }

        # Mock query_entities to return the generator
        self.mock_table_client.query_entities.return_value = massive_result_generator()

        # Call retrieve_metrics_data
        # It should now break after MAX_RETRIEVAL_LIMIT (10000)
        results = self.storage.retrieve_metrics_data("p", "b", 30)

        self.assertEqual(len(results), self.storage.MAX_RETRIEVAL_LIMIT)

    def test_get_stored_projects_limit(self):
        """Test that get_stored_projects (slow path) enforces limit"""

        # Mock exceptions to force slow path
        self.mock_table_client.get_entity.side_effect = Exception("Not found")

        # Create generator for list_entities
        def massive_project_generator():
            for i in range(20000):
                yield {
                    "PartitionKey": "pk",
                    "RowKey": f"rk_{i}",
                    "ProjectKey": f"project_{i}"
                }

        self.mock_table_client.list_entities.return_value = massive_project_generator()

        projects = self.storage.get_stored_projects()

        # Should be limited to MAX_RETRIEVAL_LIMIT
        self.assertEqual(len(projects), self.storage.MAX_RETRIEVAL_LIMIT)

if __name__ == '__main__':
    unittest.main()
