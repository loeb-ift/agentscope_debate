import subprocess
import os
import uuid
import time
from typing import Optional, Tuple

class DockerAdapter:
    """
    Adapter for managing Docker containers and executing commands within them.
    This provides a secure sandbox for running Python code.
    """
    
    def __init__(self, image_name: str = "ods-sandbox", container_name_prefix: str = "ods-worker"):
        self.image_name = image_name
        self.container_name_prefix = container_name_prefix
        self.container_id: Optional[str] = None
        self.workspace_path = os.path.abspath("./charts") # Host path to mount
        
        # Ensure workspace exists
        os.makedirs(self.workspace_path, exist_ok=True)

    def start_container(self) -> str:
        """Start a new sandbox container."""
        if self.container_id:
            return self.container_id
            
        container_name = f"{self.container_name_prefix}-{uuid.uuid4().hex[:8]}"
        
        # Build command: run detached, mount charts dir, remove on exit (optional, but good for cleanup if not using stop)
        # Actually we keep it running to execute multiple commands
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-v", f"{self.workspace_path}:/app/charts",
            # Limit resources
            "--cpus", "1.0",
            "--memory", "512m",
            self.image_name
        ]
        
        try:
            print(f"Starting Docker container: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.container_id = result.stdout.strip()
            print(f"Container started: {self.container_id}")
            
            # Wait a bit for container to be ready
            time.sleep(2) 
            return self.container_id
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to start Docker container: {e.stderr}")

    def execute_code(self, code: str, timeout: int = 30) -> str:
        """
        Execute Python code inside the container.
        
        Strategy:
        1. Write code to a temporary file inside container (or pipe it).
        2. Run `python3 <file>`.
        3. Capture stdout/stderr.
        """
        if not self.container_id:
            self.start_container()
            
        # Escape code for shell (simplified approach)
        # A better way is to write to a file first.
        
        # 1. Create a python script inside the container
        script_name = f"script_{uuid.uuid4().hex[:6]}.py"
        
        # We use `cat` to write file content. 
        # Warning: This is fragile with complex quotes. 
        # Robust way: write to local temp file, `docker cp`, then run.
        
        local_script_path = os.path.join(self.workspace_path, script_name)
        with open(local_script_path, "w") as f:
            f.write(code)
            
        # 2. Copy to container (Docker CP is not needed if we mounted the volume!)
        # Since we mounted ./charts to /app/charts, we can just put the file there.
        # But wait, execute_code usually runs in /app. 
        # Let's assume the script is in /app/charts/<script_name>
        
        container_script_path = f"/app/charts/{script_name}"
        
        # 3. Execute
        cmd = [
            "docker", "exec", 
            self.container_id,
            "python3", container_script_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = result.stdout
            if result.stderr:
                output += f"\n[Stderr]:\n{result.stderr}"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out."
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr}"
        finally:
            # Cleanup local file
            if os.path.exists(local_script_path):
                os.remove(local_script_path)

    def stop_container(self):
        """Stop and remove the container."""
        if self.container_id:
            try:
                subprocess.run(["docker", "rm", "-f", self.container_id], check=True, capture_output=True)
                print(f"Container {self.container_id} stopped and removed.")
                self.container_id = None
            except Exception as e:
                print(f"Error stopping container: {e}")

# Singleton instance for simple usage
_docker_instance = None

def get_docker_adapter():
    global _docker_instance
    if _docker_instance is None:
        _docker_instance = DockerAdapter()
    return _docker_instance
