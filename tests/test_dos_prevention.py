import unittest
from unittest.mock import MagicMock, patch, call
from azure_storage import AzureTableStorage
import hashlib

class TestDoSPrevention(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"

        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_get_stored_projects_uses_metadata_if_available(self):
        """Test that get_stored_projects uses metadata partition if migration is complete"""
        # Mock migration status entity
        migration_status = {
            'PartitionKey': 'METADATA_PROJECTS',
            'RowKey': 'MIGRATION_STATUS',
            'Status': 'Complete'
        }

        # Mock get_entity for migration status check
        self.mock_table_client.get_entity.return_value = migration_status

        # Mock project entities in metadata
        project1 = {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'hash1', 'ProjectKey': 'proj1'}
        project2 = {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'hash2', 'ProjectKey': 'proj2'}

        # Mock query_entities to return metadata list
        # It's called with "PartitionKey eq @pk"
        self.mock_table_client.query_entities.return_value = [migration_status, project1, project2]

        projects = self.storage.get_stored_projects()

        self.assertIn('proj1', projects)
        self.assertIn('proj2', projects)
        self.assertNotIn('MIGRATION_STATUS', projects)

        # Verify list_entities (full scan) was NOT called
        self.mock_table_client.list_entities.assert_not_called()

    def test_get_stored_projects_performs_scan_and_backfill_if_migration_incomplete(self):
        """Test that get_stored_projects scans and backfills if migration is incomplete"""

        # 1. Migration status check returns error (incomplete)
        self.mock_table_client.get_entity.side_effect = Exception("Not found")

        # 2. list_entities returns all data (simulation of full scan)
        self.mock_table_client.list_entities.return_value = [
            {'ProjectKey': 'projA'},
            {'ProjectKey': 'projA'}, # Duplicate
            {'ProjectKey': 'projB'}
        ]

        projects = self.storage.get_stored_projects()

        self.assertCountEqual(projects, ['projA', 'projB'])

        # Verify backfill occurred
        # upsert_entity should be called for projA, projB, and MIGRATION_STATUS

        # Calculate expected hashes
        hash_A = hashlib.sha256('projA'.encode('utf-8')).hexdigest()
        hash_B = hashlib.sha256('projB'.encode('utf-8')).hexdigest()

        # We check that upsert_entity was called with these arguments (order might vary)
        upsert_calls = self.mock_table_client.upsert_entity.call_args_list
        self.assertEqual(len(upsert_calls), 3)

        # extract the entities passed to upsert
        upserted_entities = [c[0][0] for c in upsert_calls]

        row_keys = [e['RowKey'] for e in upserted_entities]
        self.assertIn(hash_A, row_keys)
        self.assertIn(hash_B, row_keys)
        self.assertIn('MIGRATION_STATUS', row_keys)

if __name__ == '__main__':
    unittest.main()
