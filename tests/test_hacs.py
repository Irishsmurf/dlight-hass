import json
import os
import unittest

class TestHacsCompliance(unittest.TestCase):
    """Test suite to ensure HACS compliance."""

    def test_hacs_json_exists(self):
        """Check if hacs.json exists in the root."""
        self.assertTrue(os.path.exists("hacs.json"), "hacs.json missing from root")

    def test_hacs_json_content(self):
        """Check if hacs.json has required fields."""
        with open("hacs.json", "r") as f:
            data = json.load(f)
            self.assertIn("name", data, "hacs.json missing 'name' field")

    def test_manifest_json_exists(self):
        """Check if manifest.json exists in the integration directory."""
        manifest_path = "custom_components/dlight/manifest.json"
        self.assertTrue(os.path.exists(manifest_path), f"{manifest_path} missing")

    def test_manifest_json_content(self):
        """Check if manifest.json has all required HACS fields."""
        manifest_path = "custom_components/dlight/manifest.json"
        with open(manifest_path, "r") as f:
            data = json.load(f)
            required_fields = ["domain", "name", "version", "documentation", "issue_tracker", "codeowners"]
            for field in required_fields:
                self.assertIn(field, data, f"manifest.json missing required field: {field}")
            
            # Domain must match folder name
            self.assertEqual(data["domain"], "dlight", "Domain in manifest must be 'dlight' to match component folder")

    def test_directory_structure(self):
        """Check if the integration is in the correct directory."""
        self.assertTrue(os.path.exists("custom_components/dlight"), "Integration directory missing")

    def test_readme_exists(self):
        """Check if README.md exists."""
        self.assertTrue(os.path.exists("README.md"), "README.md missing from root")

if __name__ == "__main__":
    unittest.main()
