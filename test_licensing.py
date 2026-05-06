import unittest
from licensing import LicenseManager

class TestLicensing(unittest.TestCase):
    def setUp(self):
        self.lm = LicenseManager()

    def test_feature_gating(self):
        # Free Tier
        self.assertFalse(LicenseManager.is_feature_allowed("batch_processing", "Free"))
        self.assertFalse(LicenseManager.is_feature_allowed("advanced_entities", "Free"))
        
        # Pro Tier
        self.assertTrue(LicenseManager.is_feature_allowed("batch_processing", "Pro"))
        self.assertTrue(LicenseManager.is_feature_allowed("advanced_entities", "Pro"))
        self.assertFalse(LicenseManager.is_feature_allowed("custom_patterns", "Pro"))
        
        # Enterprise Tier
        self.assertTrue(LicenseManager.is_feature_allowed("batch_processing", "Enterprise"))
        self.assertTrue(LicenseManager.is_feature_allowed("custom_patterns", "Enterprise"))

    def test_activation_simulation(self):
        # Valid Pro Key
        success, tier, msg = self.lm.activate_online("PRO-123")
        self.assertTrue(success)
        self.assertEqual(tier, "Pro")
        
        # Valid Enterprise Key
        success, tier, msg = self.lm.activate_online("ENT-123")
        self.assertTrue(success)
        self.assertEqual(tier, "Enterprise")
        
        # Invalid Key
        success, tier, msg = self.lm.activate_online("INVALID")
        self.assertFalse(success)
        self.assertEqual(tier, "Free")

if __name__ == "__main__":
    unittest.main()
