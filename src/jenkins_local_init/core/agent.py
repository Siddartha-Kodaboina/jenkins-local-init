from typing import Tuple, List, Dict
from pathlib import Path
from ..core.docker import DockerManager
from ..config.manager import ConfigManager
from ..core.ssh import SSHKeyManager
from rich.console import Console
import time
import subprocess
import platform
from ..core.agent_config import JenkinsAgentConfigurator

console = Console()
class JenkinsAgent:
    def __init__(self, docker_manager: DockerManager, config_manager: ConfigManager, ssh_manager: SSHKeyManager):
        self.docker = docker_manager
        self.config = config_manager.get_config()
        self.ssh_manager = ssh_manager
        
        # Get agent configuration
        self.agent_config = self.config["infrastructure"]["agent"]
        self.network_name = self.config["infrastructure"]["network"]["name"]
        self.base_name = self.agent_config["container_name_prefix"]
        self.image = self.agent_config["image"]
        self.logs_dir = Path(self.config["directories"]["logs"])
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Get master configuration
        master_config = self.config["infrastructure"]["master"]
        self.jenkins_url = f"http://localhost:{master_config['port']}"
        self.base_ssh_port = self.agent_config["base_ssh_port"]
        
        # Initialize agent configurator with default credentials
        self.agent_configurator = JenkinsAgentConfigurator(
            self.jenkins_url,
            "admin",
            "admin"
        )


    def _get_agent_name(self, index: int) -> str:
        """Generate agent container name based on index."""
        return f"{self.base_name}-{index}"
    
    def _get_ssh_port(self, index: int) -> int:
        """Generate unique SSH port for each agent."""
        return self.base_ssh_port + (index - 1)

    def deploy_agent(self, index: int, cpu_limit: str, memory_limit: str) -> Dict[str, any]:
        """Deploy a single Jenkins agent container.
        
        Args:
            index: The index number for the agent
            cpu_limit: CPU limit for the container
            memory_limit: Memory limit for the container
            
        Returns:
            Dictionary containing deployment status and details
        """
        agent_name = self._get_agent_name(index)
        ssh_port = self._get_ssh_port(index)
        
        result = {
            'agent_name': agent_name,
            'ssh_port': ssh_port,
            'container_status': None,
            'jenkins_status': None,
            'error': None
        }

        # First, deploy the Docker container
        container_success, container_output = self._deploy_container(
            agent_name, cpu_limit, memory_limit, ssh_port
        )
        result['container_status'] = 'success' if container_success else 'failed'
        
        if not container_success:
            result['error'] = f"Container deployment failed: {container_output}"
            return result

        # Configure SSH credentials in Jenkins master (only for first agent)
        if index == 1:
            cred_success, cred_message = self.agent_configurator.configure_credentials(
                Path(self.ssh_manager.get_private_key_path())
            )
            if not cred_success:
                result['error'] = f"Failed to configure SSH credentials: {cred_message}"
                return result

        # Configure the agent in Jenkins master
        jenkins_success, jenkins_message = self.agent_configurator.configure_agent(
            agent_name,
            agent_name,  # Use container name for direct Docker network communication
            22          # Use default SSH port inside container
        )
        result['jenkins_status'] = 'success' if jenkins_success else 'failed'
        
        if not jenkins_success:
            result['error'] = f"Failed to configure agent in Jenkins: {jenkins_message}"
        
        return result

    def _deploy_container(self, agent_name: str, cpu_limit: str, memory_limit: str, ssh_port: int) -> Tuple[bool, str]:
        """Deploy the Docker container for the agent."""
        docker_gid = "999"  # default fallback
        if platform.system() == "Darwin":  # macOS
            docker_gid = "20"  # staff group ID on macOS
        else:  # Linux
            try:
                docker_gid_cmd = ["getent", "group", "docker"]
                docker_gid_result = subprocess.run(docker_gid_cmd, capture_output=True, text=True)
                if docker_gid_result.returncode == 0:
                    docker_gid = docker_gid_result.stdout.split(':')[2]
            except FileNotFoundError:
                pass
    
        command = [
            'docker', 'run',
            '-d',
            '--name', agent_name,
            '--network', self.network_name,
            '--cpus', cpu_limit,
            '-m', memory_limit,
            '-v', '/var/run/docker.sock:/var/run/docker.sock',
            '--group-add', docker_gid,
            '-v', f'{self.ssh_manager.get_private_key_path()}:/home/jenkins/.ssh/id_rsa',
            '-v', f'{self.logs_dir}:/var/log/jenkins',
            '-e', f'JENKINS_AGENT_SSH_PUBKEY={self.ssh_manager.get_public_key()}',
            '-p', f'{ssh_port}:22',  # Dynamic port mapping
            '--restart', 'unless-stopped',
            self.image
        ]
        
        success, output = self.docker.run_command(command)
        time.sleep(2)  # Wait for container to start
        _, docker_logs = self.docker.run_command(['docker', 'logs', agent_name])
        return success, f"{output}\nContainer Logs:\n{docker_logs}"

    def get_agent_logs(self, index: int) -> Tuple[bool, str]:
        """Get logs for a specific agent."""
        agent_name = self._get_agent_name(index)
        log_file = self.logs_dir / f"{agent_name}.log"
        
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    return True, f.read()
            except Exception as e:
                return False, f"Error reading log file: {str(e)}"
        
        # If log file doesn't exist, try getting logs from container
        return self.docker.run_command(['docker', 'logs', agent_name])

    def deploy_agents(self, count: int, cpu_limit: str, memory_limit: str) -> List[Dict[str, any]]:
        """Deploy multiple Jenkins agent containers.
        
        Args:
            count: Number of agents to deploy
            cpu_limit: CPU limit for each container
            memory_limit: Memory limit for each container
            
        Returns:
            List of dictionaries containing deployment status and details for each agent
        """
        console.print(f"[bold blue]Deploying {count} Jenkins agents...[/bold blue]")
        results = []
        
        for i in range(1, count + 1):
            console.print(f"\n[yellow]Deploying agent {i} of {count}...[/yellow]")
            result = self.deploy_agent(i, cpu_limit, memory_limit)
            
            # Print status
            if result['error']:
                console.print(f"[red]✗ Agent {result['agent_name']} deployment failed: {result['error']}[/red]")
            else:
                console.print(f"[green]✓ Agent {result['agent_name']} deployed successfully[/green]")
                console.print(f"  SSH Port: {result['ssh_port']}")
                console.print(f"  Container Status: {result['container_status']}")
                console.print(f"  Jenkins Status: {result['jenkins_status']}")
            
            results.append(result)
        
        # Print summary
        success_count = len([r for r in results if not r['error']])
        console.print(f"\n[bold]Deployment Summary:[/bold]")
        console.print(f"Successfully deployed: {success_count}/{count} agents")
        
        return results

    def _agent_exists(self, name: str) -> bool:
        """Check if an agent container exists."""
        success, output = self.docker.run_command([
            'docker', 'ps',
            '-a',
            '--filter', f'name=^{name}$',  # Exact name match
            '--format', '{{.Names}}'
        ])
        return success and output.strip() != ''

    def list_agents(self) -> List[Dict[str, str]]:
        """List all Jenkins agent containers and their status."""
        success, output = self.docker.run_command([
            'docker', 'ps',
            '-a',
            '--filter', f'name={self.base_name}',
            '--format', '{{.Names}}\t{{.Status}}\t{{.ID}}'
        ])
        
        agents = []
        if success and output:
            for line in output.split('\n'):
                if line:
                    name, status, container_id = line.split('\t')
                    agents.append({
                        'name': name,
                        'status': status,
                        'id': container_id
                    })
        return agents

    def remove_agent(self, index: int) -> Tuple[bool, str]:
        """Remove a specific agent container."""
        agent_name = self._get_agent_name(index)
        
        # Stop container first
        stop_success, _ = self.docker.run_command(['docker', 'stop', agent_name])
        if not stop_success:
            return False, f"Failed to stop agent {agent_name}"
            
        # Remove container
        return self.docker.run_command(['docker', 'rm', agent_name])

    def remove_all_agents(self) -> List[Tuple[bool, str]]:
        """Remove all agent containers."""
        agents = self.list_agents()
        results = []
        for agent in agents:
            success, message = self.docker.run_command(['docker', 'rm', '-f', agent['id']])
            results.append((success, message))
        return results