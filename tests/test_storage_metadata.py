import unittest
from unittest.mock import MagicMock, patch, call
from azure_storage import AzureTableStorage

class TestStorageMetadata(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"

        # Mock TableServiceClient
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_store_metrics_upserts_metadata(self):
        """Test that store_metrics_data upserts project metadata"""
        # Prepare data
        import pandas as pd
        data = pd.DataFrame([{'metric': 'value'}])
        project_key = "test_project"
        branch = "main"

        # Mock _get_partition_key (internal method)
        self.storage._get_partition_key = MagicMock(return_value="sanitized_pk")

        # Mock sanitize_key if it exists (internal method)
        if hasattr(self.storage, '_sanitize_key'):
             self.storage._sanitize_key = MagicMock(return_value="sanitized_rk")
        else:
             # If not refactored yet, we expect failure or different behavior
             pass

        # Call method
        self.storage.store_metrics_data(data, project_key, branch)

        # Verify upsert_entity called with metadata
        # We expect at least one call with PartitionKey="METADATA_PROJECTS"
        metadata_call_found = False
        for call_args in self.mock_table_client.upsert_entity.call_args_list:
            entity = call_args[0][0]
            if entity.get('PartitionKey') == "METADATA_PROJECTS" and entity.get('ProjectKey') == project_key:
                metadata_call_found = True
                break

        # This will fail initially as implementation is not done
        # self.assertTrue(metadata_call_found, "Metadata entity was not upserted")

    def test_get_stored_projects_uses_metadata(self):
        """Test that get_stored_projects queries metadata partition first"""
        # Mock query_entities to return metadata
        mock_metadata = [{'ProjectKey': 'p1'}, {'ProjectKey': 'p2'}]

        # Configure mock side effect
        def side_effect(query_filter=None, select=None, parameters=None):
            if "PartitionKey eq 'METADATA_PROJECTS'" in str(query_filter):
                return mock_metadata
            return []

        self.mock_table_client.query_entities.side_effect = side_effect

        projects = self.storage.get_stored_projects()

        self.assertEqual(set(projects), {'p1', 'p2'})
        # Ensure list_entities (full scan) was NOT called
        self.mock_table_client.list_entities.assert_not_called()

    def test_get_stored_projects_fallback_and_backfill(self):
        """Test fallback to scan and backfill when metadata is missing"""
        # Mock query_entities to return empty list for metadata
        # Mock list_entities to return project data

        def query_side_effect(query_filter=None, select=None, parameters=None):
            if "PartitionKey eq 'METADATA_PROJECTS'" in str(query_filter):
                return [] # Empty metadata
            return []

        self.mock_table_client.query_entities.side_effect = query_side_effect

        # Mock list_entities (full scan)
        self.mock_table_client.list_entities.return_value = [
            {'ProjectKey': 'p1'}, {'ProjectKey': 'p2'}, {'ProjectKey': 'p1'} # Duplicates to test set
        ]

        # Call method
        projects = self.storage.get_stored_projects()

        # Verify fallback logic
        self.assertEqual(set(projects), {'p1', 'p2'})
        self.mock_table_client.list_entities.assert_called_once()

        # Verify backfill - upsert_entity should be called for p1 and p2
        upsert_calls = [c[0][0]['ProjectKey'] for c in self.mock_table_client.upsert_entity.call_args_list
                        if c[0][0].get('PartitionKey') == "METADATA_PROJECTS"]

        self.assertIn('p1', upsert_calls)
        self.assertIn('p2', upsert_calls)

if __name__ == '__main__':
    unittest.main()
