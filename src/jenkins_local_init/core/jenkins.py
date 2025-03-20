import time
from pathlib import Path
from typing import Tuple, Optional
import subprocess
from ..core.docker import DockerManager
from ..config.manager import ConfigManager
import requests
import time
import json
from typing import Tuple, Optional, Dict

class JenkinsMaster:
    def __init__(self, docker_manager: DockerManager, config_manager: ConfigManager):
        self.docker = docker_manager
        self.config = config_manager.get_config()
        self.master_config = self.config["infrastructure"]["master"]
        
        self.container_name = self.master_config["container_name"]
        self.network_name = self.config["infrastructure"]["network"]["name"]
        self.volume_name = self.config["infrastructure"]["volume"]["name"]
        self.image = self.master_config["image"]
        self.host_port = self.master_config["port"]
        self.jnlp_port = self.master_config["jnlp_port"]
        self.jenkins_url = f"http://localhost:{self.host_port}"

    def is_running(self) -> bool:
        """Check if Jenkins master container is running."""
        success, output = self.docker.run_command([
            'docker', 'ps',
            '--filter', f'name={self.container_name}',
            '--format', '{{.Status}}'
        ])
        return success and 'Up' in output

    def deploy(self) -> Tuple[bool, str]:
        """Deploy Jenkins master container."""
        if self.is_running():
            return True, "Jenkins master is already running"

        command = [
            'docker', 'run',
            '-d',
            '--name', self.container_name,
            '--network', self.network_name,
            '-v', f'{self.volume_name}:/var/jenkins_home',
            '-p', f'{self.host_port}:8080',
            '-p', f'{self.jnlp_port}:50000',
            '--restart', 'unless-stopped',
            '-e', 'JAVA_OPTS=-Djenkins.install.runSetupWizard=false',
            '-e', 'JENKINS_OPTS=--argumentsRealm.roles.user=admin --argumentsRealm.passwd.admin=admin --argumentsRealm.roles.admin=admin',
            self.image
        ]
        
        return self.docker.run_command(command)

    def get_admin_password(self) -> Optional[str]:
        """Get initial admin password."""
        if not self.is_running():
            return None

        # Wait for password file to be created (max 30 seconds)
        for _ in range(30):
            success, output = self.docker.run_command([
                'docker', 'exec',
                self.container_name,
                'cat', '/var/jenkins_home/secrets/initialAdminPassword'
            ])
            if success:
                return output.strip()
            time.sleep(1)
        
        return None

    def stop(self) -> Tuple[bool, str]:
        """Stop Jenkins master container."""
        return self.docker.run_command(['docker', 'stop', self.container_name])

    def start(self) -> Tuple[bool, str]:
        """Start Jenkins master container."""
        return self.docker.run_command(['docker', 'start', self.container_name])
    
    def restart(self) -> Tuple[bool, str]:
        """Restart Jenkins master container."""
        stop_success, _ = self.stop()
        if not stop_success:
            return False, "Failed to stop container"
        start_success, _ = self.start()
        if not start_success:
            return False, "Failed to start container"
        return True, "Container restarted successfully"

    def remove(self) -> Tuple[bool, str]:
        """Remove Jenkins master container."""
        self.stop()
        return self.docker.run_command(['docker', 'rm', self.container_name])

    def get_logs(self) -> Tuple[bool, str]:
        """Get container logs."""
        return self.docker.run_command(['docker', 'logs', self.container_name])

    def wait_for_jenkins_ready(self, timeout: int = 180) -> bool:
        """Wait for Jenkins to be fully up and running."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.jenkins_url}/login")
                if response.status_code == 200:
                    return True
            except:
                pass
            time.sleep(5)
        return False
    
    def configure_initial_setup(self, admin_user: str, admin_password: str) -> Tuple[bool, str]:
        """Configure initial Jenkins setup."""
        if not self.wait_for_jenkins_ready():
            return False, "Jenkins did not start within timeout period"

        # initial_password = self.get_admin_password()
        # if not initial_password:
        #     return False, "Could not retrieve initial admin password"

        # Create Jenkins home directory
        success, _ = self.docker.run_command([
            'docker', 'exec',
            self.container_name,
            'mkdir', '-p', '/var/jenkins_home/init.groovy.d'
        ])
        if not success:
            return False, "Failed to create init.groovy.d directory"

        # Create initialization script
        init_script = f"""
import jenkins.model.*
import hudson.security.*
import jenkins.security.s2m.AdminWhitelistRule

def instance = Jenkins.getInstance()

// Create first admin user
def hudsonRealm = new HudsonPrivateSecurityRealm(false)
hudsonRealm.createAccount("{admin_user}", "{admin_password}")
instance.setSecurityRealm(hudsonRealm)

// Configure authorization
def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
strategy.setAllowAnonymousRead(false)
instance.setAuthorizationStrategy(strategy)

// Enable agent to master security
instance.getInjector().getInstance(AdminWhitelistRule.class).setMasterKillSwitch(false)

// Disable setup wizard
instance.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)

instance.save()
"""
        
        # Write initialization script to container
        with open('/tmp/init.groovy', 'w') as f:
            f.write(init_script)
        
        success, _ = self.docker.run_command([
            'docker', 'cp',
            '/tmp/init.groovy',
            f'{self.container_name}:/var/jenkins_home/init.groovy.d/init.groovy'
        ])
        if not success:
            return False, "Failed to copy initialization script"

        # Restart Jenkins to apply changes
        self.restart()
        
        return True, "Initial setup completed successfully"

    def install_plugins(self, admin_user: str, admin_password: str, plugins: list) -> Tuple[bool, str]:
        """Install Jenkins plugins."""
        if not self.wait_for_jenkins_ready():
            return False, "Jenkins did not start within timeout period"

        # Create a session with authentication
        session = requests.Session()
        session.auth = (admin_user, admin_password)

        # Get CSRF token (crumb)
        try:
            crumb_response = session.get(f"{self.jenkins_url}/crumbIssuer/api/json")
            if crumb_response.status_code != 200:
                return False, f"Failed to get CSRF token: {crumb_response.status_code}"
            
            crumb_data = crumb_response.json()
            crumb_header = {crumb_data['crumbRequestField']: crumb_data['crumb']}
        except Exception as e:
            return False, f"Failed to get CSRF token: {str(e)}"

        # Install each plugin
        installed_plugins = []
        failed_plugins = []

        for plugin in plugins:
            try:
                # Check if plugin is already installed
                plugin_info_url = f"{self.jenkins_url}/pluginManager/api/json?depth=1"
                plugin_info_response = session.get(plugin_info_url)
                if plugin_info_response.status_code == 200:
                    plugin_data = plugin_info_response.json()
                    installed = any(p['shortName'] == plugin for p in plugin_data.get('plugins', []))
                    
                    if installed:
                        installed_plugins.append(plugin)
                        continue

                # Install plugin
                install_url = f"{self.jenkins_url}/pluginManager/installNecessaryPlugins"
                xml_data = f'<jenkins><install plugin="{plugin}@latest" /></jenkins>'
                headers = {'Content-Type': 'text/xml'}
                headers.update(crumb_header)
                
                response = session.post(install_url, data=xml_data, headers=headers)
                
                if response.status_code in (200, 302):
                    installed_plugins.append(plugin)
                else:
                    failed_plugins.append(f"{plugin} (HTTP {response.status_code})")
            except Exception as e:
                failed_plugins.append(f"{plugin} (Error: {str(e)})")

        # Wait for plugins to be installed
        time.sleep(10)
        
        # Restart Jenkins to apply plugin changes
        self.restart()
        
        # Wait for Jenkins to come back up
        if not self.wait_for_jenkins_ready():
            return False, "Jenkins did not restart properly after plugin installation"
        
        if failed_plugins:
            return False, f"Failed to install plugins: {', '.join(failed_plugins)}"
        
        return True, f"Successfully installed plugins: {', '.join(installed_plugins)}"

