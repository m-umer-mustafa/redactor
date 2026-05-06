import json
import requests
import uuid

class LicenseManager:
    # A "Master Key" for your Phase 4B presentation
    # Entering this key will unlock everything locally
    DEMO_MASTER_KEY = "REDACTOR-PHASE4B-DEMO"

    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        # Use built-in uuid to get a unique hardware ID
        self.hw_id = str(uuid.getnode())
        
    def get_hardware_id(self):
        return self.hw_id

    def activate_online(self, license_key):
        """
        Calls Whop to verify the license key.
        Returns (success, tier, message)
        """
        url = "https://api.whop.com/api/v2/memberships/validate_license"
        
        api_header = {
            "Authorization": "Bearer apik_DyFzJoAshx9aJ_C5057022_C_04cc4ed41756aad9a78fd0573fedcc0448342e7db72c1751364afd06d1ae91",
            "Content-Type": "application/json"
        }

        payload = {
            "license_key": license_key
        }
        
        try:
            # 1. Master Key check for your presentation (Phase 4B)
            if license_key == "REDACTOR-PHASE4B-DEMO":
                return True, "Enterprise", "Master Access Granted: All features unlocked."

            # 2. Real Whop API Call
            response = requests.post(url, headers=api_header, json=payload)
            if response.status_code == 200:
                data = response.json()
                # Detect the tier from the plan name in Whop
                plan_name = data.get('plan', {}).get('name', '').lower()
                
                if 'pro' in plan_name:
                    return True, "Pro", f"Successfully activated {data['plan']['name']}!"
                else:
                    return True, "Solo", f"Successfully activated {data['plan']['name']}!"
            
            # 3. Simulated keys for quick testing
            if license_key.startswith("PRO-"):
                return True, "Pro", "Successfully activated Professional tier (Simulation)."
            elif license_key.startswith("ENT-"):
                return True, "Enterprise", "Successfully activated Enterprise tier (Simulation)."
            
            return False, "Free", "Invalid license key or membership not found."
        except Exception as e:
            return False, "Free", f"Connection error: {str(e)}"

    @staticmethod
    def is_feature_allowed(feature, current_tier):
        """
        Logic for feature gating.
        """
        tier_levels = {
            "Free": 0,
            "Pro": 1,
            "Enterprise": 2
        }
        
        feature_requirements = {
            "batch_processing": 1,
            "advanced_entities": 1,
            "custom_patterns": 2,
            "priority_support": 2
        }
        
        required_level = feature_requirements.get(feature, 0)
        user_level = tier_levels.get(current_tier, 0)
        
        return user_level >= required_level
