import unittest
from unittest.mock import MagicMock, patch, call
from azure_storage import AzureTableStorage

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

        # Mock get_entity to return migration status
        self.mock_table_client.get_entity.return_value = migration_status

        # Mock project entities in metadata
        project1 = {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'proj1', 'ProjectKey': 'proj1'}
        project2 = {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'proj2', 'ProjectKey': 'proj2'}

        # Configure mock query to return projects
        self.mock_table_client.query_entities.return_value = [migration_status, project1, project2]

        projects = self.storage.get_stored_projects()

        # Verification
        self.mock_table_client.get_entity.assert_called_with(
            partition_key='METADATA_PROJECTS',
            row_key='MIGRATION_STATUS'
        )
        self.assertIn('proj1', projects)
        self.assertIn('proj2', projects)
        self.assertNotIn('MIGRATION_STATUS', projects)

        # Verify list_entities (full scan) was NOT called
        self.mock_table_client.list_entities.assert_not_called()

    def test_get_stored_projects_performs_scan_and_backfill_if_migration_incomplete(self):
        """Test that get_stored_projects scans and backfills if migration is incomplete"""

        # 1. Migration status check raises exception (not found)
        self.mock_table_client.get_entity.side_effect = Exception("Not Found")

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
        expected_calls = [
            call({'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'projA', 'ProjectKey': 'projA', 'LastUpdated': unittest.mock.ANY}),
            call({'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'projB', 'ProjectKey': 'projB', 'LastUpdated': unittest.mock.ANY}),
            call({'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'MIGRATION_STATUS', 'Status': 'Complete', 'LastUpdated': unittest.mock.ANY})
        ]

        # We check that upsert_entity was called with these arguments (order might vary)
        # Using any_order=True if possible, but assertHasCalls works for list

        # Let's check individually to be safe against order
        upsert_calls = self.mock_table_client.upsert_entity.call_args_list
        self.assertEqual(len(upsert_calls), 3)

        # extract the entities passed to upsert
        upserted_entities = [c[0][0] for c in upsert_calls]

        row_keys = [e['RowKey'] for e in upserted_entities]
        self.assertIn('projA', row_keys)
        self.assertIn('projB', row_keys)
        self.assertIn('MIGRATION_STATUS', row_keys)

if __name__ == '__main__':
    unittest.main()
