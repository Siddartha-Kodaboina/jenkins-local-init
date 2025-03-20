import os
from pathlib import Path
from typing import Tuple
import subprocess
from ..config.manager import ConfigManager

class SSHKeyManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager.get_config()
        self.ssh_dir = Path(self.config["directories"]["ssh"])
        self.private_key_path = self.ssh_dir / "jenkins_agent"
        self.public_key_path = self.ssh_dir / "jenkins_agent.pub"

    def generate_key_pair(self) -> Tuple[bool, str]:
        """Generate a new SSH key pair for Jenkins agents."""
        try:
            # Create SSH directory if it doesn't exist
            self.ssh_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate key pair using ssh-keygen
            result = subprocess.run([
                'ssh-keygen',
                '-t', 'rsa',
                '-b', '4096',
                '-C', 'jenkins-agent@local',
                '-f', str(self.private_key_path),
                '-N', ''  # Empty passphrase
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                return False, f"Failed to generate SSH key: {result.stderr}"
            
            # Set correct permissions
            os.chmod(self.private_key_path, 0o600)
            os.chmod(self.public_key_path, 0o644)
            
            return True, "SSH key pair generated successfully"
            
        except Exception as e:
            return False, f"Error generating SSH key pair: {str(e)}"

    def get_public_key(self) -> str:
        """Get the public key content."""
        try:
            with open(self.public_key_path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def get_private_key_path(self) -> str:
        """Get the path to the private key."""
        return str(self.private_key_path)

    def keys_exist(self) -> bool:
        """Check if SSH keys already exist."""
        return self.private_key_path.exists() and self.public_key_path.exists()

    def backup_keys(self) -> Tuple[bool, str]:
        """Backup existing SSH keys."""
        try:
            if not self.keys_exist():
                return False, "No keys to backup"
            
            backup_dir = self.ssh_dir / "backup"
            backup_dir.mkdir(exist_ok=True)
            
            import shutil
            import datetime
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            shutil.copy(self.private_key_path, backup_dir / f"jenkins_agent_{timestamp}")
            shutil.copy(self.public_key_path, backup_dir / f"jenkins_agent_{timestamp}.pub")
            
            return True, "SSH keys backed up successfully"
            
        except Exception as e:
            return False, f"Error backing up SSH keys: {str(e)}"