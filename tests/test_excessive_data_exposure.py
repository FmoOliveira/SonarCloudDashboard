import unittest
from unittest.mock import MagicMock, patch
from azure_storage import AzureTableStorage

class TestExcessiveDataExposure(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_retrieve_metrics_data_excludes_sensitive_fields(self):
        """Test that retrieve_metrics_data requests only specific columns and filters results"""
        project_key = "test_project"
        branch = "main"
        days = 30

        # Mock returned entity with unexpected sensitive data
        # In a real scenario, Azure would NOT return SSN if select is used.
        # However, if the query somehow failed to filter (e.g. bug in Azure SDK or misconfiguration),
        # we want to ensure we rely on the query parameter.

        full_entity = {
            'PartitionKey': 'pk',
            'RowKey': 'rk',
            'Timestamp': 'ts',
            'ProjectKey': project_key,
            'Branch': branch,
            'Date': '2025-01-01',
            'bugs': 5,
            'vulnerabilities': 2,
            'SSN': '123-45-6789',
            'InternalNotes': 'Secret project',
            'AdminPassword': 'password123'
        }

        # We need to simulate Azure's behavior: if select is passed, return only those fields.
        def side_effect(*args, **kwargs):
            select_cols = kwargs.get('select')
            if select_cols:
                # Filter the entity
                filtered_entity = {k: v for k, v in full_entity.items() if k in select_cols or k in ['PartitionKey', 'RowKey', 'Timestamp']}
                return iter([filtered_entity])
            return iter([full_entity])

        self.mock_table_client.query_entities.side_effect = side_effect

        # Call the method
        results = self.storage.retrieve_metrics_data(project_key, branch, days)

        # Check that query_entities was called with select
        call_args = self.mock_table_client.query_entities.call_args
        self.assertIn('select', call_args.kwargs)
        select_list = call_args.kwargs['select']
        self.assertIn('bugs', select_list)
        self.assertNotIn('SSN', select_list)

        self.assertTrue(len(results) > 0)
        result = results[0]

        # Verify expected fields are present
        self.assertIn('bugs', result)
        self.assertEqual(result['bugs'], 5)
        self.assertIn('project_key', result)

        # Verify sensitive fields are ABSENT (because mock simulated Azure filtering)
        self.assertNotIn('SSN', result, "SSN leaked!")
        self.assertNotIn('InternalNotes', result, "InternalNotes leaked!")
        self.assertNotIn('AdminPassword', result, "AdminPassword leaked!")

if __name__ == '__main__':
    unittest.main()
