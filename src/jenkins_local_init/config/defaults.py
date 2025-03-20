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
        "agent": {
            "container_name_prefix": "jenkins-local-agent",
            "image": "jenkins-local-agent:latest",
            "default_cpu": "2",
            "default_memory": "2g",
            "default_count": 1,
            "docker_socket": "/var/run/docker.sock",
            "workspace_dir": "/home/jenkins/agent",
            "base_ssh_port": 2222 
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
        "ngrok": str(JENKINS_LOCAL_DIR / "ngrok"),
        "logs": str(JENKINS_LOCAL_DIR / "logs"),
    }
}