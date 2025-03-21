import subprocess
import json
import time
import os
import requests
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from ..config.manager import ConfigManager

class NgrokManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager.get_config()
        self.ngrok_dir = Path(self.config["directories"]["ngrok"])
        self.ngrok_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.ngrok_dir / "ngrok.yml"
        self.auth_token_file = self.ngrok_dir / "auth_token"
        self.api_url = "http://localhost:4040/api"
        
    def is_installed(self) -> bool:
        """Check if ngrok is installed on the system."""
        try:
            result = subprocess.run(
                ["ngrok", "version"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def is_authenticated(self) -> bool:
        """Check if an auth token is configured."""
        return self.auth_token_file.exists()
    
    def save_auth_token(self, token: str) -> None:
        """Save the ngrok auth token."""
        with open(self.auth_token_file, 'w') as f:
            f.write(token)
        
        # Set appropriate permissions
        os.chmod(self.auth_token_file, 0o600)
    
    def get_auth_token(self) -> Optional[str]:
        """Get the saved auth token if it exists."""
        if not self.auth_token_file.exists():
            return None
        
        with open(self.auth_token_file, 'r') as f:
            return f.read().strip()
    
    def authenticate(self, token: str) -> Tuple[bool, str]:
        """Authenticate with ngrok using the provided token."""
        try:
            self.save_auth_token(token)
            
            # Test the token by running ngrok config check
            result = subprocess.run(
                ["ngrok", "config", "add-authtoken", token],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                return True, "Authentication successful"
            else:
                return False, f"Authentication failed: {result.stderr}"
        except Exception as e:
            return False, f"Error during authentication: {str(e)}"
    
    def is_running(self) -> bool:
        """Check if ngrok is currently running."""
        try:
            response = requests.get(f"{self.api_url}/tunnels")
            return response.status_code == 200
        except:
            return False
    
    def get_public_url(self) -> Optional[str]:
        """Get the public URL of the active tunnel if any."""
        if not self.is_running():
            return None
            
        try:
            response = requests.get(f"{self.api_url}/tunnels")
            if response.status_code != 200:
                return None
                
            tunnels = response.json().get('tunnels', [])
            for tunnel in tunnels:
                # Find any https tunnel
                if tunnel.get('proto') == 'https':
                    return tunnel.get('public_url')
            
            return None
        except:
            return None
    
    def start_tunnel(self, port: int) -> Tuple[bool, str]:
        """Start an ngrok tunnel to the specified port.
        
        Args:
            port: The local port to tunnel to (Jenkins web interface)
            
        Returns:
            Tuple of (success, message)
        """
        if not self.is_installed():
            return False, "Ngrok is not installed. Please install it first."
            
        if not self.is_authenticated():
            return False, "Ngrok is not authenticated. Please run 'jenkins-local-init ngrok auth' first."
            
        if self.is_running():
            public_url = self.get_public_url()
            if public_url:
                return True, f"Ngrok is already running. Public URL: {public_url}"
            else:
                self.stop_tunnel()
        
        try:
            # Start ngrok in the background
            subprocess.Popen(
                [
                    "ngrok", "http", 
                    f"{port}", 
                    "--log", f"{self.ngrok_dir}/ngrok.log",
                    "--log-format", "json",
                    "--log-level", "info"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for ngrok to start
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(1)
                if self.is_running():
                    public_url = self.get_public_url()
                    if public_url:
                        return True, f"Ngrok tunnel started. Public URL: {public_url}"
            
            return False, "Failed to start ngrok tunnel. Check logs for details."
        except Exception as e:
            return False, f"Error starting ngrok tunnel: {str(e)}"
    
    def stop_tunnel(self) -> Tuple[bool, str]:
        """Stop any running ngrok tunnels."""
        try:
            # Find ngrok process
            if os.name == 'nt':  # Windows
                subprocess.run(["taskkill", "/f", "/im", "ngrok.exe"], 
                               capture_output=True, check=False)
            else:  # Unix/Linux/Mac
                subprocess.run(["pkill", "-f", "ngrok"], 
                               capture_output=True, check=False)
            
            # Wait for ngrok to stop
            max_attempts = 5
            for attempt in range(max_attempts):
                time.sleep(1)
                if not self.is_running():
                    return True, "Ngrok tunnel stopped successfully"
            
            return False, "Failed to stop ngrok tunnel"
        except Exception as e:
            return False, f"Error stopping ngrok tunnel: {str(e)}"
    
    def get_tunnel_status(self) -> Dict[str, Any]:
        """Get detailed status of the ngrok tunnel."""
        status = {
            "running": self.is_running(),
            "public_url": None,
            "tunnels": []
        }
        
        if not status["running"]:
            return status
            
        try:
            response = requests.get(f"{self.api_url}/tunnels")
            if response.status_code == 200:
                tunnels_data = response.json().get('tunnels', [])
                status["tunnels"] = tunnels_data
                
                # Find the https tunnel
                for tunnel in tunnels_data:
                    if tunnel.get('proto') == 'https':
                        status["public_url"] = tunnel.get('public_url')
                        break
        except:
            pass
            
        return status
    
    def update_jenkins_url(self, jenkins_master, admin_user: str, admin_password: str) -> Tuple[bool, str]:
        """Update Jenkins URL configuration to use the ngrok public URL.
        
        Args:
            jenkins_master: JenkinsMaster instance
            admin_user: Jenkins admin username
            admin_password: Jenkins admin password
            
        Returns:
            Tuple of (success, message)
        """
        public_url = self.get_public_url()
        if not public_url:
            return False, "No active ngrok tunnel found"
            
        try:
            # Create a simple Groovy script to update the Jenkins URL
            script_content = f"""
#!/usr/bin/env groovy
import jenkins.model.JenkinsLocationConfiguration

def locationConfig = JenkinsLocationConfiguration.get()
locationConfig.setUrl("{public_url}")
locationConfig.save()
println("Jenkins URL updated to: " + locationConfig.getUrl())
"""
            
            # Write the script to a temporary file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.groovy') as temp_file:
                temp_file.write(script_content)
                script_path = temp_file.name
            
            try:
                # Copy the script to the container
                container_script_path = "/tmp/update_jenkins_url.groovy"
                success, output = jenkins_master.docker.run_command([
                    'docker', 'cp',
                    script_path,
                    f'{jenkins_master.container_name}:{container_script_path}'
                ])
                
                if not success:
                    os.unlink(script_path)
                    return False, f"Failed to copy script to container: {output}"
                
                # Execute the script in the container using cat to pipe it directly to the groovy command
                success, output = jenkins_master.docker.run_command([
                    'docker', 'exec',
                    jenkins_master.container_name,
                    'bash', '-c', f"echo '{script_content}' | java -jar /var/jenkins_home/war/WEB-INF/jenkins-cli.jar -s http://localhost:8080/ -auth {admin_user}:{admin_password} groovy ="
                ])
                
                # Clean up the temporary file
                os.unlink(script_path)
                
                if "Jenkins URL updated to" in output:
                    return True, f"Jenkins URL updated to {public_url}"
                else:
                    # Try an alternative approach by directly modifying the config.xml file
                    # Get the current config.xml
                    success, config_xml = jenkins_master.docker.run_command([
                        'docker', 'exec',
                        jenkins_master.container_name,
                        'cat', '/var/jenkins_home/jenkins.model.JenkinsLocationConfiguration.xml'
                    ])
                    
                    if success and config_xml:
                        # Update the URL in the config.xml
                        import re
                        updated_config = re.sub(
                            r'<jenkinsUrl>.*?</jenkinsUrl>',
                            f'<jenkinsUrl>{public_url}</jenkinsUrl>',
                            config_xml
                        )
                        
                        # Write the updated config to a temporary file
                        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_config:
                            temp_config.write(updated_config)
                            config_path = temp_config.name
                        
                        # Copy the updated config back to the container
                        success, output = jenkins_master.docker.run_command([
                            'docker', 'cp',
                            config_path,
                            f'{jenkins_master.container_name}:/var/jenkins_home/jenkins.model.JenkinsLocationConfiguration.xml'
                        ])
                        
                        # Clean up the temporary config file
                        os.unlink(config_path)
                        
                        if success:
                            # Restart Jenkins to apply the changes
                            jenkins_master.restart()
                            return True, f"Jenkins URL updated to {public_url} (via config.xml)"
                    
                    return False, f"Failed to update Jenkins URL: {output}"
            finally:
                # Ensure the temporary file is deleted
                if os.path.exists(script_path):
                    os.unlink(script_path)
                    
            return False, "Failed to update Jenkins URL"
        except Exception as e:
            return False, f"Error updating Jenkins URL: {str(e)}"
