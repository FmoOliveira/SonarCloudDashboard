import unittest
from unittest.mock import MagicMock, patch
from azure_storage import AzureTableStorage
import pandas as pd

class TestDoSPrevention(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_store_metrics_updates_metadata(self):
        """Test that storing metrics also updates the metadata partition"""
        df = pd.DataFrame([{'coverage': 80.0}])
        self.storage.store_metrics_data(df, "test_project", "main")

        # Check if upsert_entity was called for metadata
        # We expect at least one upsert for the project metadata
        # The mock might be called multiple times (for metrics entities)
        # We need to find the call with PartitionKey='METADATA_PROJECTS'

        found_metadata_update = False
        for call in self.mock_table_client.upsert_entity.call_args_list:
            args, kwargs = call
            entity = args[0] if args else kwargs.get('entity')
            if entity and entity.get('PartitionKey') == 'METADATA_PROJECTS' and entity.get('ProjectKey') == 'test_project':
                found_metadata_update = True
                break

        self.assertTrue(found_metadata_update, "Metadata update not found in store_metrics_data calls")

    def test_get_stored_projects_uses_metadata(self):
        """Test that get_stored_projects uses metadata partition when migration is complete"""
        # Setup mock to return "Complete" for migration status
        def get_entity_side_effect(partition_key, row_key):
            if partition_key == 'METADATA_PROJECTS' and row_key == 'MIGRATION_STATUS':
                return {'Status': 'Complete'}
            raise Exception("Entity not found")

        self.mock_table_client.get_entity.side_effect = get_entity_side_effect

        # Call the method
        self.storage.get_stored_projects()

        # Verify it called query_entities with PartitionKey='METADATA_PROJECTS'
        found_metadata_query = False
        for call in self.mock_table_client.query_entities.call_args_list:
            kwargs = call.kwargs
            query_filter = kwargs.get('query_filter') or (call.args[0] if call.args else "")
            parameters = kwargs.get('parameters')

            if "PartitionKey eq @pk" in query_filter and parameters and parameters.get('pk') == 'METADATA_PROJECTS':
                found_metadata_query = True
                break

        self.assertTrue(found_metadata_query, "Did not query metadata partition")

        # Verify it did NOT call list_entities (full scan)
        # Note: In the new implementation, it shouldn't call list_entities if migration is complete.
        self.mock_table_client.list_entities.assert_not_called()

    def test_get_stored_projects_falls_back_to_scan(self):
        """Test that get_stored_projects falls back to scan if metadata missing"""
        # Setup mock to raise exception for migration status (simulating missing)
        self.mock_table_client.get_entity.side_effect = Exception("Not found")

        self.storage.get_stored_projects()

        # Verify it CALLED list_entities
        self.mock_table_client.list_entities.assert_called()
