import unittest
from unittest.mock import MagicMock, patch
from azure_storage import AzureTableStorage
import pandas as pd
import hashlib

class TestMetadataFix(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_store_metrics_uses_hashed_rowkey_for_metadata(self):
        """Verify that store_metrics_data uses SHA256 hashed RowKey for metadata partition"""
        project_key = "project/A"
        expected_hash = hashlib.sha256(project_key.encode('utf-8')).hexdigest()

        df = pd.DataFrame([{'vulnerabilities': 10}])

        self.storage.store_metrics_data(df, project_key)

        # Check calls to upsert_entity
        upsert_calls = self.mock_table_client.upsert_entity.call_args_list

        found_metadata_update = False
        for call in upsert_calls:
            entity = call[0][0]
            if entity['PartitionKey'] == "METADATA_PROJECTS":
                found_metadata_update = True
                self.assertEqual(entity['RowKey'], expected_hash, "Metadata RowKey should be SHA256 hash of project_key")
                self.assertEqual(entity['ProjectKey'], project_key, "Metadata entity should contain original ProjectKey")

        self.assertTrue(found_metadata_update, "Metadata partition update not found")

    def test_get_stored_projects_returns_correct_project_keys(self):
        """Verify that get_stored_projects reads ProjectKey from entities, not RowKey"""

        # Mock migration status as Complete
        self.mock_table_client.get_entity.return_value = {'Status': 'Complete'}

        # Mock metadata query results
        project_key_1 = "project/A"
        project_key_2 = "project#B"
        hash_1 = hashlib.sha256(project_key_1.encode('utf-8')).hexdigest()
        hash_2 = hashlib.sha256(project_key_2.encode('utf-8')).hexdigest()

        mock_entities = [
            {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': hash_1, 'ProjectKey': project_key_1},
            {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': hash_2, 'ProjectKey': project_key_2},
            {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'MIGRATION_STATUS'} # Marker
        ]

        self.mock_table_client.query_entities.return_value = mock_entities

        projects = self.storage.get_stored_projects()

        self.assertIn(project_key_1, projects)
        self.assertIn(project_key_2, projects)
        self.assertNotIn(hash_1, projects) # Should return original key, not hash
        self.assertEqual(len(projects), 2)

    def test_delete_project_data_uses_hashed_rowkey(self):
        """Verify that delete_project_data uses SHA256 hashed RowKey for metadata deletion"""
        project_key = "project/A"
        expected_hash = hashlib.sha256(project_key.encode('utf-8')).hexdigest()

        # Mock queries to return empty result (project data deleted)
        # First query: list entities to delete (we mock empty so we skip main loop)
        # Second query: check remaining data (mock empty to trigger metadata deletion)
        self.mock_table_client.query_entities.side_effect = [[], []]

        self.storage.delete_project_data(project_key)

        # Check delete_entity calls
        delete_calls = self.mock_table_client.delete_entity.call_args_list

        found_metadata_delete = False
        for call in delete_calls:
            kwargs = call.kwargs
            if kwargs.get('partition_key') == "METADATA_PROJECTS":
                found_metadata_delete = True
                self.assertEqual(kwargs.get('row_key'), expected_hash, "Metadata deletion RowKey should be SHA256 hash")

        self.assertTrue(found_metadata_delete, "Metadata partition deletion not found")

if __name__ == '__main__':
    unittest.main()
