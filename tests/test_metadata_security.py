import unittest
from azure_storage import AzureTableStorage
from unittest.mock import MagicMock, patch
import hashlib

class TestMetadataSecurity(unittest.TestCase):
    def setUp(self):
        self.connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
        self.table_name = "TestTable"
        with patch('azure.data.tables.TableServiceClient.from_connection_string') as mock_service_client:
            self.mock_table_client = MagicMock()
            mock_service_client.return_value.get_table_client.return_value = self.mock_table_client
            self.storage = AzureTableStorage(self.connection_string, self.table_name)

    def test_metadata_key_collision_prevention(self):
        """Test that _get_metadata_row_key produces unique keys for colliding project names"""
        project1 = "project/A"
        project2 = "project_A"

        # Verify old behavior causes collision (demonstration of vulnerability)
        old_key1 = self.storage._get_partition_key(project1)
        old_key2 = self.storage._get_partition_key(project2)
        print(f"Old Keys: {old_key1} vs {old_key2}")
        self.assertEqual(old_key1, old_key2, "Old method should cause collision")

        # Verify new behavior prevents collision
        # This assumes _get_metadata_row_key is implemented
        if hasattr(self.storage, '_get_metadata_row_key'):
            new_key1 = self.storage._get_metadata_row_key(project1)
            new_key2 = self.storage._get_metadata_row_key(project2)
            print(f"New Keys: {new_key1} vs {new_key2}")
            self.assertNotEqual(new_key1, new_key2, "New method should produce unique keys")
        else:
            self.fail("_get_metadata_row_key not implemented")

    def test_store_metrics_data_uses_secure_hash(self):
        """
        Verify that store_metrics_data now uses _get_metadata_row_key (SHA256) for metadata RowKey.
        This confirms the fix for the collision vulnerability.
        """
        project_key = "project/A"
        # Calculate expected sanitized key (vulnerable behavior)
        expected_weak_key = self.storage._sanitize_key(project_key) # "project_A"

        # Calculate secure hashed key (desired behavior)
        expected_secure_key = hashlib.sha256(project_key.encode('utf-8')).hexdigest()

        # Mock data
        import pandas as pd
        df = pd.DataFrame([{'coverage': 80.0}])

        # Call the method
        self.storage.store_metrics_data(df, project_key)

        # Check the upsert_entity call for metadata partition
        # We look for the call with PartitionKey="METADATA_PROJECTS"
        metadata_call = None
        for call_args in self.mock_table_client.upsert_entity.call_args_list:
            entity = call_args[0][0]
            if entity['PartitionKey'] == "METADATA_PROJECTS" and entity['ProjectKey'] == project_key:
                metadata_call = entity
                break

        self.assertIsNotNone(metadata_call, "Metadata upsert not found")

        # ASSERTION: verify it matches the secure hash
        self.assertEqual(metadata_call['RowKey'], expected_secure_key,
                         "Code should use secure hash for metadata RowKey")

        self.assertNotEqual(metadata_call['RowKey'], expected_weak_key,
                            "Code should NOT use weak sanitization")

if __name__ == '__main__':
    unittest.main()
