
import requests
import pandas as pd
from typing import Dict, Any, List
from api.config import Config
from mars.types.errors import ToolRecoverableError

class FREDAdapter:
    """
    Adapter for St. Louis Fed (FRED) API.
    Provides macroeconomic data and time series.
    """
    def __init__(self):
        self.api_key = Config.FRED_API_KEY
        self.base_url = "https://api.stlouisfed.org/fred"
        self.name = "fred"

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("FRED_API_KEY not configured in .env")
        
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                detail = response.json().get("error_message", str(e))
                raise ToolRecoverableError(f"FRED API Error: {detail}")
            raise e
        except Exception as e:
            raise ToolRecoverableError(f"FRED Connection Error: {str(e)}")

class FREDSeriesSearch(FREDAdapter):
    def __init__(self):
        super().__init__()
        self.name = "fred.search_series"
        self.description = "Search for economic series IDs on FRED by keywords (e.g., 'inflation', 'gdp')."
        self.schema = {
            "type": "object",
            "properties": {
                "search_text": {"type": "string", "description": "The keywords to search for."},
                "limit": {"type": "integer", "description": "Maximum number of results (default 10).", "default": 10}
            },
            "required": ["search_text"]
        }

    def describe(self) -> str:
        return self.description

    def invoke(self, search_text: str, limit: int = 10) -> Dict[str, Any]:
        params = {
            "search_text": search_text,
            "limit": limit,
            "order_by": "popularity",
            "sort_order": "desc"
        }
        data = self._request("series/search", params)
        series = data.get("seriess", [])
        return {
            "results": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "observation_start": s.get("observation_start"),
                    "observation_end": s.get("observation_end"),
                    "frequency": s.get("frequency"),
                    "units": s.get("units")
                } for s in series
            ]
        }

class FREDSeriesObservations(FREDAdapter):
    def __init__(self):
        super().__init__()
        self.name = "fred.get_series_observations"
        self.description = "Get observation data (values) for a specific economic series ID."
        self.schema = {
            "type": "object",
            "properties": {
                "series_id": {"type": "string", "description": "The series ID (e.g., 'CPIAUCSL' for inflation)."},
                "observation_start": {"type": "string", "description": "Start date (YYYY-MM-DD)."},
                "observation_end": {"type": "string", "description": "End date (YYYY-MM-DD)."},
                "frequency": {"type": "string", "description": "Optional frequency (d, w, m, q, sa, a)."},
                "limit": {"type": "integer", "description": "Max observations (default 100).", "default": 100}
            },
            "required": ["series_id"]
        }

    def describe(self) -> str:
        return self.description

    def invoke(self, series_id: str, observation_start: str = None, observation_end: str = None, frequency: str = None, limit: int = 100) -> Dict[str, Any]:
        params = {
            "series_id": series_id,
            "limit": limit,
            "sort_order": "desc" # Latest first
        }
        if observation_start: params["observation_start"] = observation_start
        if observation_end: params["observation_end"] = observation_end
        if frequency: params["frequency"] = frequency
        
        data = self._request("series/observations", params)
        obs = data.get("observations", [])
        
        return {
            "series_id": series_id,
            "units": data.get("units"),
            "data": [
                {
                    "date": o.get("date"),
                    "value": o.get("value")
                } for o in obs
            ]
        }

class FREDLatestRelease(FREDAdapter):
    def __init__(self):
        super().__init__()
        self.name = "fred.get_latest_release"
        self.description = "Get the latest value and release date for a specific economic series ID."
        self.schema = {
            "type": "object",
            "properties": {
                "series_id": {"type": "string", "description": "The series ID (e.g., 'FEDFUNDS')."}
            },
            "required": ["series_id"]
        }

    def describe(self) -> str:
        return self.description

    def invoke(self, series_id: str) -> Dict[str, Any]:
        params = {
            "series_id": series_id,
            "limit": 1,
            "sort_order": "desc"
        }
        data = self._request("series/observations", params)
        obs = data.get("observations", [])
        if not obs:
            return {"error": "No data found for this series."}
        
        latest = obs[0]
        return {
            "series_id": series_id,
            "latest_date": latest.get("date"),
            "latest_value": latest.get("value"),
            "units": data.get("units")
        }
