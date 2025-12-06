from typing import Dict, Any
import requests
from adapters.tool_adapter import ToolAdapter

class HTTPToolAdapter(ToolAdapter):
    def __init__(self, name: str, description: str, api_config: Dict[str, Any], schema: Dict[str, Any], version: str = "v1"):
        self._name = name
        self._description = description
        self._api_config = api_config
        self._schema = schema
        self._version = version

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        return self._description

    @property
    def schema(self) -> Dict[str, Any]:
        return self._schema

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        url = self._api_config.get("url")
        method = self._api_config.get("method", "GET").upper()
        headers = self._api_config.get("headers", {})
        
        # Simple parameter handling: GET -> params, POST -> json
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=kwargs)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=kwargs)
            else:
                return {"error": f"Unsupported method: {method}"}
                
            response.raise_for_status()
            try:
                return response.json()
            except:
                return {"result": response.text}
                
        except Exception as e:
            return {"error": str(e)}