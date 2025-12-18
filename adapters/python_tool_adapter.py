from typing import Dict, Any, Optional
from adapters.tool_adapter import ToolAdapter
from adapters.docker_adapter import get_docker_adapter
import logging
import re
import os

class PythonToolAdapter(ToolAdapter):
    """
    增強版 Python Tool Adapter
    支援:
    1. 本地安全執行 (Legacy mode)
    2. Docker 沙箱執行 (Secure mode)
    3. Matplotlib 圖片輸出自動處理
    """
    
    def __init__(self, name: str, description: str, python_code: str, schema: Dict[str, Any], version: str = "v1", use_docker: bool = True):
        self._name = name
        self._description = description
        self._python_code = python_code
        self._schema = schema
        self._version = version
        self._use_docker = use_docker
        self._compiled_func = None
        
        if not self._use_docker:
            self._compile_code()
        else:
            self._docker = get_docker_adapter()

    def _compile_code(self):
        """Legacy compilation for trusted internal tools"""
        try:
            local_scope = {}
            exec(self._python_code, {}, local_scope)
            if 'main' in local_scope:
                self._compiled_func = local_scope['main']
            else:
                for key, value in local_scope.items():
                    if callable(value):
                        self._compiled_func = value
                        break
            if not self._compiled_func:
                raise ValueError("No callable function found (define 'main').")
        except Exception as e:
            logging.error(f"Failed to compile Python tool {self._name}: {e}")
            self._compiled_func = None

    @property
    def name(self) -> str: return self._name

    @property
    def version(self) -> str: return self._version

    @property
    def description(self) -> str: return self._description

    @property
    def schema(self) -> Dict[str, Any]: return self._schema

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute the tool. 
        If use_docker is True, it wraps the code execution in the sandbox.
        """
        if not self._use_docker:
            # Local Execution
            if not self._compiled_func:
                return {"error": "Tool code failed to compile."}
            try:
                result = self._compiled_func(**kwargs)
                return {"result": result}
            except Exception as e:
                return {"error": f"Execution failed: {str(e)}"}
        
        else:
            # Docker Execution
            # We assume kwargs contains the 'code' to execute if this is a generic executor,
            # OR we construct the code to call the function defined in self._python_code with kwargs.
            
            # Case 1: Generic Executor (e.g., name="python.execute")
            if self.name == "python.execute":
                code_to_run = kwargs.get("code", "")
                if not code_to_run:
                    return {"error": "No code provided for execution."}
                
                # Enhance code to handle matplotlib plots
                code_to_run = self._inject_matplotlib_patch(code_to_run)
                
                result = self._docker.execute_code(code_to_run)
                
                # Check for generated images
                images = self._scan_generated_images(result)
                
                return {
                    "result": result,
                    "images": images
                }
            
            # Case 2: Specific Tool (Wraps a function)
            else:
                # We need to run self._python_code inside docker, then call main(**kwargs)
                # Construct a runner script
                params_str = ", ".join([f"{k}={repr(v)}" for k, v in kwargs.items()])
                runner_code = f"""
{self._python_code}

if __name__ == "__main__":
    try:
        res = main({params_str})
        print(res)
    except Exception as e:
        print(f"Error: {{e}}")
"""
                result = self._docker.execute_code(runner_code)
                return {"result": result}

    def _inject_matplotlib_patch(self, code: str) -> str:
        """Inject code to save plots automatically instead of showing them."""
        patch = """
import matplotlib.pyplot as plt
import os
import uuid

def save_plot_patch():
    if plt.get_fignums():
        filename = f"plot_{uuid.uuid4().hex[:8]}.png"
        path = os.path.join("/app/charts", filename)
        plt.savefig(path)
        print(f"[IMAGE_GENERATED]: {{filename}}")
        plt.close()

# Patch plt.show
plt.show = save_plot_patch
"""
        return patch + "\n" + code + "\n" + "save_plot_patch()" # Ensure saving at the end

    def _scan_generated_images(self, output: str) -> list:
        """Parse stdout for [IMAGE_GENERATED]: filename tags."""
        images = []
        matches = re.findall(r'\[IMAGE_GENERATED\]: (.*?.png)', output)
        for filename in matches:
            # Map container path to host path
            # Container: /app/charts/xxx.png
            # Host: ./charts/xxx.png (as configured in DockerAdapter)
            host_path = f"./charts/{filename.strip()}"
            images.append(host_path)
        return images
