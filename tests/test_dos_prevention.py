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

        # Mock project entities in metadata
        project1 = {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'proj1', 'ProjectKey': 'proj1'}
        project2 = {'PartitionKey': 'METADATA_PROJECTS', 'RowKey': 'proj2', 'ProjectKey': 'proj2'}

        # Configure mock to return migration status first, then projects
        # We need to simulate the sequence of calls

        # The implementation will likely do:
        # 1. Get migration status
        # 2. Query metadata partition

        # We can use side_effect to return different values for different calls
        # But query_entities arguments differ.

        def query_side_effect(**kwargs):
            query_filter = kwargs.get('query_filter')
            parameters = kwargs.get('parameters')

            if "RowKey eq @rk" in query_filter and parameters.get('rk') == 'MIGRATION_STATUS':
                return [migration_status]

            if "PartitionKey eq @pk" in query_filter and parameters.get('pk') == 'METADATA_PROJECTS':
                # Should filter out MIGRATION_STATUS in the code or here?
                # The query usually fetches everything in partition.
                return [migration_status, project1, project2]

            return []

        self.mock_table_client.query_entities.side_effect = query_side_effect

        projects = self.storage.get_stored_projects()

        self.assertIn('proj1', projects)
        self.assertIn('proj2', projects)
        self.assertNotIn('MIGRATION_STATUS', projects)

        # Verify list_entities (full scan) was NOT called
        self.mock_table_client.list_entities.assert_not_called()

    def test_get_stored_projects_performs_scan_and_backfill_if_migration_incomplete(self):
        """Test that get_stored_projects scans and backfills if migration is incomplete"""

        # 1. Migration status check returns empty
        def query_side_effect(**kwargs):
             return []

        self.mock_table_client.query_entities.side_effect = query_side_effect

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
