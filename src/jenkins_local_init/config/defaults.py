from pathlib import Path

# Base directories
HOME_DIR = Path.home()
JENKINS_LOCAL_DIR = HOME_DIR / ".jenkins-local"

# Default configuration
DEFAULT_CONFIG = {
    "infrastructure": {
        "master": {
            "port": 8080,
            "jnlp_port": 50000,
            "memory": "2g",
            "cpus": 2,
            "container_name": "jenkins-local-master",
            "image": "jenkins/jenkins:lts"
        },
        "network": {
            "name": "jenkins-local-net"
        },
        "volume": {
            "name": "jenkins-local-data"
        }
    },
    "directories": {
        "base": str(JENKINS_LOCAL_DIR),
        "config": str(JENKINS_LOCAL_DIR / "config"),
        "ssh": str(JENKINS_LOCAL_DIR / "ssh"),
        "volumes": str(JENKINS_LOCAL_DIR / "volumes"),
        "ngrok": str(JENKINS_LOCAL_DIR / "ngrok")
    }
}