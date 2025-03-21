import subprocess
from typing import Tuple, List, Optional
import json
from pathlib import Path

class DockerManager:
    @staticmethod
    def run_command(command: List[str]) -> Tuple[bool, str]:
        """Run a docker command and return result."""
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def check_docker_running(self) -> bool:
        """Check if Docker daemon is running."""
        success, _ = self.run_command(['docker', 'info'])
        return success

    def create_network(self, name: str) -> Tuple[bool, str]:
        """Create a Docker network if it doesn't exist."""
        # Check if network exists
        success, output = self.run_command([
            'docker', 'network', 'ls',
            '--format', '{{.Name}}',
            '--filter', f'name=^{name}$'
        ])
        
        if not success:
            return False, output
            
        if name in output:
            return True, f"Network {name} already exists"
            
        # Create network
        return self.run_command(['docker', 'network', 'create', name])

    def create_volume(self, name: str) -> Tuple[bool, str]:
        """Create a Docker volume if it doesn't exist."""
        # Check if volume exists
        success, output = self.run_command([
            'docker', 'volume', 'ls',
            '--format', '{{.Name}}',
            '--filter', f'name=^{name}$'
        ])
        
        if not success:
            return False, output
            
        if name in output:
            return True, f"Volume {name} already exists"
            
        # Create volume
        return self.run_command(['docker', 'volume', 'create', name])

    def backup_volume(self, volume_name: str, backup_path: Path) -> Tuple[bool, str]:
        """Backup a Docker volume."""
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        command = [
            'docker', 'run', '--rm',
            '-v', f'{volume_name}:/source:ro',
            '-v', f'{backup_path.parent}:/backup',
            'alpine', 'tar', 'czf',
            f'/backup/{backup_path.name}',
            '-C', '/source', '.'
        ]
        
        return self.run_command(command)

    def restore_volume(self, volume_name: str, backup_path: Path) -> Tuple[bool, str]:
        """Restore a Docker volume from backup."""
        if not backup_path.exists():
            return False, f"Backup file {backup_path} does not exist"
            
        command = [
            'docker', 'run', '--rm',
            '-v', f'{volume_name}:/target',
            '-v', f'{backup_path.parent}:/backup',
            'alpine', 'sh', '-c',
            f'cd /target && tar xzf /backup/{backup_path.name}'
        ]
        
        return self.run_command(command)
        
    def check_image_exists(self, image_name: str) -> bool:
        """Check if a Docker image exists locally.
        
        Args:
            image_name: Name of the image to check
            
        Returns:
            True if the image exists, False otherwise
        """
        success, output = self.run_command([
            'docker', 'images',
            '--format', '{{.Repository}}:{{.Tag}}',
            '--filter', f'reference={image_name}'
        ])
        
        return success and output.strip() != ''
        
    def build_image(self, dockerfile_path: Path, image_name: str, context_path: Optional[Path] = None) -> Tuple[bool, str]:
        """Build a Docker image from a Dockerfile.
        
        Args:
            dockerfile_path: Path to the Dockerfile
            image_name: Name to give the built image
            context_path: Path to the build context (defaults to dockerfile directory)
            
        Returns:
            Tuple of (success, message)
        """
        if not dockerfile_path.exists():
            return False, f"Dockerfile not found at {dockerfile_path}"
            
        # If no context path is provided, use the Dockerfile's directory
        if context_path is None:
            context_path = dockerfile_path.parent
            
        command = [
            'docker', 'build',
            '-t', image_name,
            '-f', str(dockerfile_path),
            str(context_path)
        ]
        
        return self.run_command(command)