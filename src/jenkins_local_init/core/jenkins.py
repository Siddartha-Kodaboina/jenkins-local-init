import time
from pathlib import Path
from typing import Tuple, Optional
import subprocess
from ..core.docker import DockerManager
from ..config.manager import ConfigManager

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

    def remove(self) -> Tuple[bool, str]:
        """Remove Jenkins master container."""
        self.stop()
        return self.docker.run_command(['docker', 'rm', self.container_name])

    def get_logs(self) -> Tuple[bool, str]:
        """Get container logs."""
        return self.docker.run_command(['docker', 'logs', self.container_name])