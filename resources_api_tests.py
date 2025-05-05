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
        response = requests.get(f"{self.base_url}/resources/find-resource-by-id", params={"id": resource_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["id"], resource_id)

    def test_get_resource_by_id_with_version(self):
        """Test retrieving a specific version of a resource."""
        resource_id = "arm-hello64-static"
        resource_version = "1.0.0"
        response = requests.get(f"{self.base_url}/resources/find-resource-by-id", params={"id": resource_id, "resource_version": resource_version})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], resource_id)
        self.assertEqual(data[0]["resource_version"], resource_version)

    def test_get_resource_by_id_not_found(self):
        """Test retrieving a resource that does not exist."""
        resource_id= "non-existent-resource"
        response = requests.get(f"{self.base_url}/resources/find-resource-by-id",  params={"id": resource_id})
        self.assertEqual(response.json()["error"], f"Resource with ID '{resource_id}' not found")
        self.assertEqual(response.status_code, 404)

    def test_get_resource_by_id_valid_id_invalid_version(self):
        """Test retrieving a resource whose id exists but hte version doesnt exist."""
        resource_id = "arm-hello64-static"
        resource_version = "1.1.1"
        response = requests.get(f"{self.base_url}/resources/find-resource-by-id", params={"id": resource_id, "resource_version": resource_version})
        self.assertEqual(response.json()["error"], f"Resource with ID '{resource_id}' not found")
        self.assertEqual(response.status_code, 404)

    def test_get_resources_by_batch(self):
        """Test retrieving multiple resources by batch with correct id-version pairing."""
        resource_pairs = [
            ("riscv-ubuntu-20.04-boot", "3.0.0"),
            ("arm-hello64-static", "1.0.0")
        ]
        query_string = "&".join([f"id={id}&version={version}" for id, version in resource_pairs])
        url = f"{self.base_url}/resources/find-resources-in-batch?{query_string}"
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
        url = f"{self.base_url}/resources/find-resources-in-batch?{query_string}"
        response = requests.get(url)

        self.assertEqual(response.status_code, 404)

    def test_search_basic_contains_str(self):
        """Test basic search with a contains-str parameter."""
        params = {
            "contains-str": "arm-hello64-static"
        }
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check that results are returned
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["id"], "arm-hello64-static")

    def test_search_with_single_filter(self):
        """Test search with a single filter criterion."""
        params = {
            "contains-str": "boot",
            "must-include": "architecture,x86"
        }
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Validate results match filter criteria
        for resource in data:
            self.assertEqual(resource["architecture"], "x86")
            self.assertIn("boot", resource["id"])

    def test_search_with_multiple_filters(self):
        """Test search with multiple filter criteria."""
        params = {
            "contains-str": "ubuntu",
            "must-include": "category,workload;architecture,RISCV"
        }
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Validate results match filter criteria
        for resource in data:
            self.assertEqual(resource["category"], "workload")
            self.assertEqual(resource["architecture"], "RISCV")
            self.assertIn("ubuntu", resource["id"].lower())

    def test_search_with_gem5_version_filter(self):
        """Test search with gem5_versions filter."""
        params = {
            "contains-str": "resource",
            "must-include": "gem5_versions,22.0"
        }
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Validate results match filter criteria
        for resource in data:
            self.assertIn("22.0", resource["gem5_versions"])

    def test_search_pagination(self):
        """Test pagination functionality."""
        # First page
        params_page1 = {
            "contains-str": "resource",
            "page": 1,
            "page-size": 2
        }
        response_page1 = requests.get(f"{self.base_url}/resources/search", params=params_page1)
        
        self.assertEqual(response_page1.status_code, 200)
        data_page1 = response_page1.json()
        
        # Second page
        params_page2 = {
            "contains-str": "resource",
            "page": 2,
            "page-size": 2
        }
        response_page2 = requests.get(f"{self.base_url}/resources/search", params=params_page2)
        
        self.assertEqual(response_page2.status_code, 200)
        data_page2 = response_page2.json()
        
        # Ensure we have resources to check
        if len(data_page1) > 0 and len(data_page2) > 0:
            # Ensure pages are different
            first_page_ids = {r["id"] for r in data_page1}
            second_page_ids = {r["id"] for r in data_page2}
            self.assertTrue(len(first_page_ids.intersection(second_page_ids)) == 0)

    def test_search_no_results(self):
        """Test search with no matching results."""
        params = {
            "contains-str": "non-existent-resource-that-should-not-exist-anywhere"
        }
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Validate empty results
        self.assertEqual(len(data), 0)

    def test_search_invalid_filter(self):
        """Test search with invalid filter format."""
        params = {
            "contains-str": "resource",
            "must-include": "invalid-filter-format"
        }
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        # Expecting a 400 Bad Request for invalid filter format
        self.assertEqual(response.status_code, 400)

    def test_search_missing_required_parameter(self):
        """Test search without the required contains-str parameter."""
        params = {}
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        # Expecting a 400 Bad Request for missing required parameter
        self.assertEqual(response.status_code, 400)

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        params1 = {
            "contains-str": "ARM-HELLO64-STATIC"  # Uppercase
        }
        params2 = {
            "contains-str": "arm-hello64-static"  # Lowercase
        }
        
        response1 = requests.get(f"{self.base_url}/resources/search", params=params1)
        response2 = requests.get(f"{self.base_url}/resources/search", params=params2)
        
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Both searches should return the same results
        self.assertEqual(len(data1), len(data2))
        if len(data1) > 0 and len(data2) > 0:
            self.assertEqual(data1[0]["id"], data2[0]["id"])

    def test_search_multiple_gem5_versions(self):
        """Test search with multiple gem5 versions in filter."""
        params = {
            "contains-str": "resource",
            "must-include": "gem5_versions,22.0,23.0"
        }
        response = requests.get(f"{self.base_url}/resources/search", params=params)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Resources should have at least one of the specified gem5 versions
        for resource in data:
            gem5_versions = set(resource["gem5_versions"])
            self.assertTrue(len({"22.0", "23.0"}.intersection(gem5_versions)) > 0)


if __name__ == "__main__":
    unittest.main()
