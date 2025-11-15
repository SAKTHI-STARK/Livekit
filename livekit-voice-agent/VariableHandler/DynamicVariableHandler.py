import re
import os
import json
from typing import Dict, Tuple, Optional

class DynamicVariableExtractor:
    VARIABLE_PATTERN = r"\{(.*?)\}"
    @staticmethod
    def extract(text: str):
        """Return list of variable names found inside { }."""
        return re.findall(DynamicVariableExtractor.VARIABLE_PATTERN, text)
    
class DynamicVariableHandler:
    def __init__(self):
        self.variables = {}

    @staticmethod
    def load_user_data(file_path: str = "user_data.json") -> Dict:
        if not os.path.exists(file_path):
            print(f"[WARNING] JSON metadata file missing: {file_path}")
            return {}

        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Error loading metadata JSON from {file_path}: {e}")
            return {}

    def set_variable(self, name: str, value):
        """Set a single variable."""
        self.variables[name] = value

    def get_variable(self, name: str):
        """Get a single variable value."""
        return self.variables.get(name, None)

    def resolve_text(self, text: str) -> str:
        if not text:
            return ""
        
        def replace_variable(match):
            var_name = match.group(1)
            return str(self.get_variable(var_name) or f"{{{var_name}}}")

        return re.sub(DynamicVariableExtractor.VARIABLE_PATTERN, replace_variable, text)

    def load_and_resolve(
        self,
        user_name: str,
        first_message: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_data_file: str = "user_data.json",
    ) -> Tuple[str, str]:
        all_user_data = self.load_user_data(user_data_file)
        user_data = all_user_data.get(user_name, {})
        
        # Populate variables
        self.set_variable("user_name", user_name)
        self.set_variable("expiry_data", user_data.get("expiry_date"))
        self.set_variable("date_of_birth", user_data.get("date_of_birth"))
        self.set_variable("policy_number", user_data.get("policy_number"))
        self.set_variable("monthly_premium_amt", user_data.get("monthly_premium_amt"))
        self.set_variable("excess_amt", user_data.get("excess_amt"))
        
        # Resolve and return both strings
        resolved_first_message = self.resolve_text(first_message) if first_message else ""
        resolved_system_prompt = self.resolve_text(system_prompt) if system_prompt else ""
        
        return resolved_first_message, resolved_system_prompt
