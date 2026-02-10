import unittest
from unittest.mock import MagicMock, patch
from azure_storage import AzureTableStorage
import pandas as pd

class TestAzureStorageSanitization(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"

        # Mock TableServiceClient
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)
            # Manually attach mock client
            self.storage.table_client = self.mock_table_client

    def test_store_metrics_data_sanitizes_partition_key(self):
        """Test that store_metrics_data sanitizes invalid characters in PartitionKey"""
        project_key = "my-project"
        branch = "feature/login" # Contains invalid '/'

        df = pd.DataFrame([{
            'metric': 'bugs',
            'value': 10,
            'bugs': 10,
            'date': '2025-01-01'
        }])

        # Call the method
        self.storage.store_metrics_data(df, project_key, branch)

        # Check create_entity call
        if self.mock_table_client.create_entity.called:
            call_args = self.mock_table_client.create_entity.call_args
            entity = call_args[0][0]
            partition_key = entity['PartitionKey']

            # Should not contain '/'
            self.assertNotIn('/', partition_key)
            # Should be sanitized (e.g. replaced with '_')
            self.assertIn('_', partition_key)
            print(f"Sanitized PartitionKey: {partition_key}")
        else:
            # Maybe update_entity was called? Or batch logic?
            # The code uses create_entity individually in a loop
            self.fail("create_entity was not called")

    def test_retrieve_metrics_data_sanitizes_partition_key(self):
        """Test that retrieve_metrics_data uses sanitized PartitionKey"""
        project_key = "my-project"
        branch = "feature/login"
        days = 30

        self.storage.retrieve_metrics_data(project_key, branch, days)

        call_args = self.mock_table_client.query_entities.call_args
        parameters = call_args.kwargs.get('parameters')

        pk = parameters['pk']
        self.assertNotIn('/', pk)
        self.assertIn('_', pk)
        print(f"Retrieve sanitized PK: {pk}")

    def test_delete_project_data_sanitizes_partition_key(self):
        """Test that delete_project_data uses sanitized PartitionKey"""
        project_key = "my-project"
        branch = "feature/login"

        self.storage.delete_project_data(project_key, branch)

        call_args = self.mock_table_client.query_entities.call_args
        parameters = call_args.kwargs.get('parameters')

        pk = parameters['pk']
        self.assertNotIn('/', pk)
        self.assertIn('_', pk)
        print(f"Delete sanitized PK: {pk}")

    def test_partition_key_sanitizes_control_characters(self):
        """Test that PartitionKey sanitizes control characters"""
        project_key = "project"
        branch = "branch\nwith\tcontrol"

        # Test directly or via method
        # Since _get_partition_key is internal, let's test via delete_project_data
        self.storage.delete_project_data(project_key, branch)

        call_args = self.mock_table_client.query_entities.call_args
        parameters = call_args.kwargs.get('parameters')
        pk = parameters['pk']

        # Should replace \n and \t with _
        self.assertNotIn('\n', pk)
        self.assertNotIn('\t', pk)
        self.assertIn('_', pk)
        print(f"Control chars sanitized PK: {repr(pk)}")

if __name__ == '__main__':
    unittest.main()
