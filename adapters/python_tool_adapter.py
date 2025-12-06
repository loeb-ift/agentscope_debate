from typing import Dict, Any
from adapters.tool_adapter import ToolAdapter
import logging

class PythonToolAdapter(ToolAdapter):
    def __init__(self, name: str, description: str, python_code: str, schema: Dict[str, Any], version: str = "v1"):
        self._name = name
        self._description = description
        self._python_code = python_code
        self._schema = schema
        self._version = version
        self._compiled_func = None
        self._compile_code()

    def _compile_code(self):
        try:
            # Create a localized dictionary for execution
            local_scope = {}
            # Execute the code string
            exec(self._python_code, {}, local_scope)
            
            # Assume the main function is named 'main' or match the tool name (simplified: look for 'main' or the first function)
            if 'main' in local_scope:
                self._compiled_func = local_scope['main']
            else:
                # Find first callable
                for key, value in local_scope.items():
                    if callable(value):
                        self._compiled_func = value
                        break
            
            if not self._compiled_func:
                raise ValueError("No callable function found in provided Python code (define a 'main' function).")
                
        except Exception as e:
            logging.error(f"Failed to compile Python tool {self._name}: {e}")
            self._compiled_func = None

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
        if not self._compiled_func:
            return {"error": "Tool code failed to compile or initialize."}
        
        try:
            result = self._compiled_func(**kwargs)
            return {"result": result}
        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}