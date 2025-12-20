
import requests
from typing import Dict, Any, List

class WorldBankAdapter:
    """
    Adapter for World Bank Open Data API.
    Provides global economic indicators.
    """
    def __init__(self):
        self.base_url = "https://api.worldbank.org/v2"
        self.name = "worldbank"

    def _request(self, endpoint: str, params: Dict[str, Any] = None) -> List[Any]:
        if params is None:
            params = {}
        params["format"] = "json"
        
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            # World Bank API returns [metadata, actual_data]
            if isinstance(data, list) and len(data) > 1:
                return data[1]
            return data
        except Exception as e:
            return [{"error": f"World Bank API Error: {str(e)}"}]

class WorldBankInflationTool:
    def __init__(self):
        self.adapter = WorldBankAdapter()
        self.name = "worldbank.global_inflation"
        self.description = "Get global inflation data (Consumer Price Index %) from World Bank for all countries."
        self.schema = {
            "type": "object",
            "properties": {
                "country_code": {"type": "string", "description": "ISO country code (default 'all').", "default": "all"},
                "date_range": {"type": "string", "description": "Year range (e.g., '2020:2024')."},
                "per_page": {"type": "integer", "description": "Items per page (default 50).", "default": 50}
            }
        }

    def describe(self) -> str:
        return self.description

    def invoke(self, country_code: str = "all", date_range: str = None, per_page: int = 50) -> Dict[str, Any]:
        endpoint = f"country/{country_code}/indicator/FP.CPI.TOTL.ZG"
        params = {"per_page": per_page}
        if date_range:
            params["date"] = date_range
            
        data = self.adapter._request(endpoint, params)
        
        return {
            "indicator": "FP.CPI.TOTL.ZG",
            "name": "Inflation, consumer prices (annual %)",
            "results": [
                {
                    "country": item.get("country", {}).get("value"),
                    "countryiso3code": item.get("countryiso3code"),
                    "date": item.get("date"),
                    "value": item.get("value")
                } for item in data if isinstance(item, dict)
            ]
        }
