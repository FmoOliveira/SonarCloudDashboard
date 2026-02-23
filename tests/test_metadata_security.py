import unittest
from azure_storage import AzureTableStorage
from unittest.mock import MagicMock, patch

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

if __name__ == '__main__':
    unittest.main()
