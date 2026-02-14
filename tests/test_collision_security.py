import unittest
from unittest.mock import MagicMock, patch
from azure_storage import AzureTableStorage

class TestAzureStorageCollisionSecurity(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"

        # Mock TableServiceClient
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_retrieve_metrics_data_prevents_collision(self):
        """Test that retrieve_metrics_data filters by ProjectKey and Branch to prevent collisions"""
        project_key = "my_project"
        branch = "main"
        days = 30

        # Call the method
        self.storage.retrieve_metrics_data(project_key, branch, days)

        # Check the call arguments
        call_args = self.mock_table_client.query_entities.call_args
        query_filter = call_args.kwargs.get('query_filter')
        if not query_filter and len(call_args[0]) > 0:
            query_filter = call_args[0][0]

        parameters = call_args.kwargs.get('parameters')

        print(f"Retrieve Query: {query_filter}")
        print(f"Parameters: {parameters}")

        # Assert filters are present
        self.assertIn("ProjectKey eq @project_key", query_filter)
        self.assertIn("Branch eq @branch", query_filter)

        # Assert parameters are correct
        self.assertEqual(parameters['project_key'], project_key)
        self.assertEqual(parameters['branch'], branch)

    def test_delete_project_data_prevents_collision(self):
        """Test that delete_project_data filters by ProjectKey and Branch to prevent collisions"""
        project_key = "my"
        branch = "project_main" # Collides with my_project/main

        self.storage.delete_project_data(project_key, branch)

        found_call = False
        for call_args in self.mock_table_client.query_entities.call_args_list:
            query_filter = call_args.kwargs.get('query_filter')
            if not query_filter and len(call_args[0]) > 0:
                query_filter = call_args[0][0]

            if "PartitionKey eq @pk" in query_filter and "ProjectKey eq @project_key" in query_filter:
                found_call = True
                parameters = call_args.kwargs.get('parameters')

                print(f"Delete Query: {query_filter}")
                print(f"Parameters: {parameters}")

                # Assert filters are present
                self.assertIn("ProjectKey eq @project_key", query_filter)
                self.assertIn("Branch eq @branch", query_filter)

                # Assert parameters are correct
                self.assertEqual(parameters['project_key'], project_key)
                self.assertEqual(parameters['branch'], branch)
                break

        self.assertTrue(found_call, "Collision prevention query not found")

if __name__ == '__main__':
    unittest.main()
