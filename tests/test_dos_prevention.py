import unittest
from unittest.mock import MagicMock, patch, call
from azure_storage import AzureTableStorage

class TestDoSPrevention(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"

        # Patch the TableServiceClient
        self.patcher = patch('azure.data.tables.TableServiceClient.from_connection_string')
        self.mock_service_client_cls = self.patcher.start()
        self.mock_service_client = MagicMock()
        self.mock_service_client_cls.return_value = self.mock_service_client

        self.mock_table_client = MagicMock()
        self.mock_service_client.get_table_client.return_value = self.mock_table_client

        self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def tearDown(self):
        self.patcher.stop()

    def test_get_stored_projects_migration_logic(self):
        """Test that get_stored_projects performs migration when metadata is missing"""
        # 1. Simulate NO migration status
        self.mock_table_client.get_entity.side_effect = Exception("Not found")

        # 2. Simulate full scan results
        mock_entities = [
            {'ProjectKey': 'project1'},
            {'ProjectKey': 'project2'},
            {'ProjectKey': 'project1'}
        ]
        self.mock_table_client.list_entities.return_value = mock_entities

        # Call method
        projects = self.storage.get_stored_projects()

        # Verify full scan was called
        self.mock_table_client.list_entities.assert_called_with(select='ProjectKey')

        # Verify metadata backfill occurred
        # Expect upsert_entity calls for project1, project2, and MIGRATION_STATUS
        upsert_calls = self.mock_table_client.upsert_entity.call_args_list

        # Check that we upserted project metadata
        # Note: Order is not guaranteed for set iteration, so we check existence
        project_keys_upserted = []
        migration_status_upserted = False

        for call_args in upsert_calls:
            entity = call_args[0][0] # First arg is entity
            if entity['RowKey'] == 'MIGRATION_STATUS':
                migration_status_upserted = True
                self.assertEqual(entity['Status'], 'Complete')
            else:
                project_keys_upserted.append(entity['ProjectKey'])
                self.assertEqual(entity['PartitionKey'], 'METADATA_PROJECTS')

        self.assertTrue(migration_status_upserted, "Migration status should be marked complete")
        self.assertEqual(set(project_keys_upserted), {'project1', 'project2'})

        # Verify result
        self.assertEqual(set(projects), {'project1', 'project2'})

    def test_get_stored_projects_fast_path(self):
        """Test that get_stored_projects uses metadata partition when migrated"""
        # 1. Simulate migration status COMPLETE
        self.mock_table_client.get_entity.return_value = {'Status': 'Complete'}

        # 2. Simulate metadata query results
        mock_metadata = [
            {'ProjectKey': 'project1'},
            {'ProjectKey': 'project2'}
        ]
        self.mock_table_client.query_entities.return_value = mock_metadata

        # Call method
        projects = self.storage.get_stored_projects()

        # Verify get_entity called for migration status
        self.mock_table_client.get_entity.assert_called_with(
            partition_key='METADATA_PROJECTS',
            row_key='MIGRATION_STATUS'
        )

        # Verify query_entities called (Fast Path)
        self.mock_table_client.query_entities.assert_called()
        call_args = self.mock_table_client.query_entities.call_args
        self.assertIn("PartitionKey eq @pk", call_args.kwargs['query_filter'])
        self.assertEqual(call_args.kwargs['parameters']['pk'], 'METADATA_PROJECTS')

        # Verify list_entities (scan) NOT called
        self.mock_table_client.list_entities.assert_not_called()

        # Verify result
        self.assertEqual(set(projects), {'project1', 'project2'})

if __name__ == '__main__':
    unittest.main()
