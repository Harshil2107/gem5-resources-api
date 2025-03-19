import unittest
import requests
import os

class TestResourcesAPIIntegration(unittest.TestCase):
    """Integration tests for the Resources API"""

    @classmethod
    def setUpClass(cls):
        """Set up the API base URL before running tests."""
        cls.base_url = os.getenv("API_BASE_URL", "http://localhost:7071/api")

    def test_get_resource_by_id(self):
        """Test retrieving a resource by ID."""
        resource_id = "riscv-ubuntu-20.04-boot"
        response = requests.get(f"{self.base_url}/resources/{resource_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["id"], resource_id)

    def test_get_resource_by_id_with_version(self):
        """Test retrieving a specific version of a resource."""
        resource_id = "arm-hello64-static"
        resource_version = "1.0.0"
        response = requests.get(f"{self.base_url}/resources/{resource_id}", params={"resource_version": resource_version})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], resource_id)
        self.assertEqual(data[0]["resource_version"], resource_version)

    def test_get_resource_by_id_not_found(self):
        """Test retrieving a resource that does not exist."""
        response = requests.get(f"{self.base_url}/resources/non-existent-resource")
        self.assertEqual(response.status_code, 404)

    def test_get_resources_by_batch(self):
        """Test retrieving multiple resources by batch with correct id-version pairing."""
        resource_pairs = [
            ("riscv-ubuntu-20.04-boot", "3.0.0"),
            ("arm-hello64-static", "1.0.0")
        ]
        query_string = "&".join([f"id={id}&version={version}" for id, version in resource_pairs])
        url = f"{self.base_url}/resources/search-by-ids?{query_string}"
        response = requests.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[1]["id"], "riscv-ubuntu-20.04-boot")
        self.assertEqual(data[1]["resource_version"], "3.0.0")
        self.assertEqual(data[0]["id"], "arm-hello64-static")
        self.assertEqual(data[0]["resource_version"], "1.0.0")


    def test_get_resources_by_batch_not_found(self):
        """Test batch retrieval where one or more resources are missing."""
        resource_pairs = [
            ("arm-hello64-static", "1.0.0"),
            ("non-existent", "9.9.9")
        ]
        query_string = "&".join([f"id={id}&version={version}" for id, version in resource_pairs])
        url = f"{self.base_url}/resources/search-by-ids?{query_string}"
        response = requests.get(url)

        self.assertEqual(response.status_code, 404)

    # def test_search_resources_basic(self):
    #     """Test searching for resources by name."""
    #     params = {"contains-str": "resource"}
    #     response = requests.get(f"{self.base_url}/resources/search", params=params)

    #     self.assertEqual(response.status_code, 200)
    #     data = response.json()
    #     self.assertIn("results", data)
    #     self.assertGreater(len(data["results"]), 0)

    # def test_search_resources_with_filters(self):
    #     """Test searching with filters."""
    #     params = {
    #         "contains-str": "resource",
    #         "must-include": "category,workload;architecture,x86;gem5_versions,22.0",
    #         "page": 1,
    #         "page-size": 2
    #     }
    #     response = requests.get(f"{self.base_url}/resources/search", params=params)

    #     self.assertEqual(response.status_code, 200)
    #     data = response.json()
    #     self.assertIn("results", data)
    #     self.assertGreater(len(data["results"]), 0)
    #     self.assertEqual(data["results"][0]["category"], "workload")

    # def test_search_resources_invalid_filter(self):
    #     """Test searching with an invalid filter field."""
    #     params = {
    #         "contains-str": "resource",
    #         "must-include": "invalid_field,value"
    #     }
    #     response = requests.get(f"{self.base_url}/resources/search", params=params)

    #     self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
