
import requests
from typing import Dict, Any, List

class OECDAdapter:
    """
    Adapter for OECD SDMX Data API (2024 JSON standard).
    Provides specialized economic and social indicators for member countries.
    """
    def __init__(self):
        # .Stat Suite RESTful API compliant URL
        # Note: OECD public endpoint often uses /public/rest
        self.base_url = "https://sdmx.oecd.org/public/rest"
        self.name = "oecd"

    def _request(self, dataflow: str, key: str = "all", params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executes a request to the OECD SDMX-JSON API (.Stat Suite standard).
        Endpoint pattern: data/{agencyID},{dataflowID},{version}/{key}
        """
        if params is None:
            params = {}
        
        # Default to JSON format as per .Stat Suite documentation
        params["format"] = "jsondata"
        
        # Standard Dataflow ID often includes Agency (defaulting to OECD)
        if "," not in dataflow:
            full_dataflow = f"OECD,{dataflow},latest"
        else:
            full_dataflow = dataflow

        # For .Stat Suite, format=jsondata is common
        if "format" not in params:
            params["format"] = "jsondata"

        url = f"{self.base_url}/data/{full_dataflow}/{key}"
        try:
            print(f"DEBUG: OECD Request URL: {url} Params: {params}")
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"OECD API Error: {str(e)}", "url": url}

class OECDDataTool:
    def __init__(self):
        self.adapter = OECDAdapter()
        self.name = "oecd.get_data"
        self.description = "Retrieve specialized economic data from OECD using .Stat Suite RESTful parameters."
        self.schema = {
            "type": "object",
            "properties": {
                "dataflow": {
                    "type": "string",
                    "description": "The Dataflow ID (e.g., 'DSD_G20_PRICES@DF_G20_PRICES').",
                    "default": "DSD_G20_PRICES@DF_G20_PRICES"
                },
                "filter_key": {
                    "type": "string",
                    "description": "SDMX filter key (e.g., 'FRA.CP.ALC'). Use 'all' for complete set.",
                    "default": "all"
                },
                "start_period": {"type": "string", "description": "Start year (e.g., '2023')."},
                "end_period": {"type": "string", "description": "End year (e.g., '2024')."},
                "dimension_at_observation": {
                    "type": "string",
                    "description": "Dimension to use at observation level (default 'AllDimensions').",
                    "default": "AllDimensions"
                }
            },
            "required": ["dataflow"]
        }

    def describe(self) -> str:
        return self.description

    def invoke(self, dataflow: str, filter_key: str = "all", start_period: str = None, end_period: str = None, dimension_at_observation: str = "AllDimensions") -> Dict[str, Any]:
        params = {"dimensionAtObservation": dimension_at_observation}
        if start_period: params["startPeriod"] = start_period
        if end_period: params["endPeriod"] = end_period
        
        raw_data = self.adapter._request(dataflow, filter_key, params)
        
        if "error" in raw_data:
            return raw_data

        # Basic SDMX-JSON Parser (Simplified for Agent readability)
        # We extract observations and link them to dimensions
        try:
            # Extract main data structure
            # Check for error in response object (OECD can return 200 with error msg in JSON)
            if "errors" in raw_data:
                 return {"error": f"OECD API Error: {raw_data.get('errors')}"}

            data_sets = raw_data.get("dataSets", [])
            structures = raw_data.get("structure", {})
            obs_dimensions = structures.get("dimensions", {}).get("observation", [])
            
            # Extract dimension values map for better context
            dim_map = {}
            for i, dim in enumerate(obs_dimensions):
                dim_id = dim.get("id")
                values = [v.get("name") or v.get("id") for v in dim.get("values", [])]
                dim_map[i] = {"id": dim_id, "values": values}
            
            results = []
            if data_sets:
                observations = data_sets[0].get("observations", {})
                for key_indices, value_list in observations.items():
                    # key_indices is like "0:0:0"
                    indices = [int(idx) for idx in key_indices.split(":")]
                    
                    # Map indices to actual dimension names/values
                    context = {}
                    for pos, val_idx in enumerate(indices):
                        if pos in dim_map:
                            d_info = dim_map[pos]
                            d_name = d_info["id"]
                            d_val = d_info["values"][val_idx] if val_idx < len(d_info["values"]) else f"idx_{val_idx}"
                            context[d_name] = d_val

                    val = value_list[0] if value_list else None
                    results.append({
                        "value": val,
                        "context": context
                    })
            
            return {
                "dataflow": dataflow,
                "note": "SDMX-JSON observations retrieved and mapped to dimensions.",
                "results": results[:30] # Increased limit slightly for better coverage
            }
        except Exception as e:
            return {"error": f"Parsing Error: {str(e)}", "raw_preview": str(raw_data)[:200]}

class OECDSearchTool:
    def __init__(self):
        self.name = "oecd.search_datasets"
        self.description = "Search for available OECD Dataflow IDs and descriptions using keywords."
        self.schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to search for (e.g., 'education', 'health')."}
            },
            "required": ["query"]
        }

    def describe(self) -> str:
        return self.description

    def invoke(self, query: str) -> Dict[str, Any]:
        # Note: OECD SDMX API doesn't have a direct 'search' endpoint like FRED.
        # We provide a curated list of high-value Dataflows and recommend using SearXNG for others.
        curated_dataflows = {
            "inflation": "DSD_G20_PRICES@DF_G20_PRICES",
            "unemployment": "DSD_LFS@DF_LFS_INDIC",
            "gdp": "DSD_NAMAIN1@DF_TABLE1",
            "health": "DSD_HEALTH_STAT@DF_HEALTH_STAT",
            "education": "DSD_EAG_FIN_ENT@DF_FIN_SOURCE"
        }
        
        matches = []
        q_lower = query.lower()
        for k, v in curated_dataflows.items():
            if q_lower in k or q_lower in v.lower():
                matches.append({"category": k, "dataflow_id": v})
        
        return {
            "matches": matches,
            "instruction": "If no match found, use 'searxng.search' to find the 'OECD Dataflow ID' for your specific topic."
        }
