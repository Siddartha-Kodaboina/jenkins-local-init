import yaml
from pathlib import Path
from typing import Dict, Any

from .defaults import DEFAULT_CONFIG, JENKINS_LOCAL_DIR

class ConfigManager:
    def __init__(self):
        self.config_file = JENKINS_LOCAL_DIR / "config" / "config.yaml"
        self.config = DEFAULT_CONFIG
        if self.config_file.exists():
            self.load_config()
            

    def init_directories(self) -> None:
        """Initialize all required directories."""
        for dir_path in self.config["directories"].values():
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    def save_config(self) -> None:
        """Save current configuration to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.safe_dump(self.config, f, default_flow_style=False)

    def load_config(self) -> None:
        """Load configuration from file if exists."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config:
                    self.config.update(loaded_config)

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        self.config.update(new_config)
        self.save_config()

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config