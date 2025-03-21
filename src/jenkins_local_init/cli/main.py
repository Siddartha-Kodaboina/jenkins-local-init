import click
from rich.console import Console
from rich.traceback import install
from ..config.manager import ConfigManager
from pathlib import Path
import os
from ..core.docker import DockerManager
from ..core.jenkins import JenkinsMaster
from ..core.ssh import SSHKeyManager
from ..core.agent import JenkinsAgent
from ..core.agent_config import JenkinsAgentConfigurator
from ..cli.logo import display_logo

# Install rich traceback handling
install()
console = Console()
config_manager = ConfigManager()
docker_manager = DockerManager()
jenkins_master = JenkinsMaster(docker_manager, config_manager)
ssh_manager = SSHKeyManager(config_manager)
agent_manager = JenkinsAgent(docker_manager, config_manager, ssh_manager)

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Jenkins Local Init - Set up Jenkins infrastructure locally on macOS."""
    pass

@cli.group()
def ssh():
    """Manage SSH keys for Jenkins agents."""
    pass
  
@cli.group()
def master():
    """Manage Jenkins master container."""
    pass

@master.command()
@click.option('--port', type=int, help='Custom port for Jenkins web interface')
@click.option('--jnlp-port', type=int, help='Custom port for JNLP agents')
@click.option('--admin-user', default='admin', help='Admin username')
@click.option('--admin-password', help='Admin password')
def deploy(port, jnlp_port, admin_user, admin_password):
    """Deploy Jenkins master container."""
    try:
        # Update ports if provided
        if port or jnlp_port:
            config = config_manager.get_config()
            if port:
                config["infrastructure"]["master"]["port"] = port
            if jnlp_port:
                config["infrastructure"]["master"]["jnlp_port"] = jnlp_port
            config_manager.update_config(config)
            
            # Reinitialize Jenkins master with new config
            global jenkins_master
            jenkins_master = JenkinsMaster(docker_manager, config_manager)

        # Check Docker daemon
        if not docker_manager.check_docker_running():
            console.print("[bold red]Error: Docker daemon is not running[/bold red]")
            return

        # Initialize network and volume if they don't exist
        docker_manager.create_network("jenkins-local-net")
        docker_manager.create_volume("jenkins-local-data")

        # Deploy master
        console.print("[bold blue]Deploying Jenkins master...[/bold blue]")
        success, message = jenkins_master.deploy()
        
        if success:
            console.print("[green]✓[/green] Jenkins master deployed successfully")
            
            # Configure initial setup
            if admin_password:
                console.print("\n[bold blue]Configuring initial setup...[/bold blue]")
                success, message = jenkins_master.configure_initial_setup(admin_user, admin_password)
                if success:
                    console.print("[green]✓[/green] Initial setup completed")
                    console.print("\n[bold blue]Jenkins is ready![/bold blue]")
                    console.print(f"Access Jenkins at: http://localhost:{jenkins_master.host_port}")
                    console.print(f"Username: {admin_user}")
                    console.print(f"Password: {admin_password}")
                else:
                    console.print(f"[red]✗[/red] Initial setup failed: {message}")
            else:
                # Show initial admin password as before
                console.print("\n[bold yellow]No admin credentials provided.[/bold yellow]")
                console.print("Jenkins will start with setup wizard.")
                password = jenkins_master.get_admin_password()
                if password:
                    console.print("[green]✓[/green] Jenkins is ready!")
                    console.print("\n[bold yellow]Initial Admin Password:[/bold yellow]")
                    console.print(f"[bold white]{password}[/bold white]")
                    console.print("\n[bold blue]Access Jenkins at:[/bold blue]")
                    console.print(f"http://localhost:{jenkins_master.host_port}")
                else:
                    console.print("[red]✗[/red] Could not retrieve admin password")

        else:
            console.print(f"[red]✗[/red] Deployment failed: {message}")

    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@master.command()
def status():
    """Check Jenkins master status."""
    try:
        if jenkins_master.is_running():
            console.print("[green]✓[/green] Jenkins master is running")
            console.print("\n[bold blue]Container Logs:[/bold blue]")
            _, logs = jenkins_master.get_logs()
            console.print(logs)
        else:
            console.print("[red]✗[/red] Jenkins master is not running")
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@master.command()
@click.argument('action', type=click.Choice(['start', 'stop', 'restart']))
def control(action):
    """Control Jenkins master container (start/stop/restart)."""
    try:
        if action == 'start':
            success, message = jenkins_master.start()
        elif action == 'stop':
            success, message = jenkins_master.stop()
        else:  # restart
            jenkins_master.stop()
            success, message = jenkins_master.start()

        if success:
            console.print(f"[green]✓[/green] Successfully {action}ed Jenkins master")
        else:
            console.print(f"[red]✗[/red] Action failed: {message}")
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")


@cli.group()
def docker():
    """Manage Docker resources for Jenkins infrastructure."""
    pass

@docker.command()
def init():
    """Initialize Docker network and volume."""
    try:
        # Check Docker daemon
        if not docker_manager.check_docker_running():
            console.print("[bold red]Error: Docker daemon is not running[/bold red]")
            return

        # Create network
        success, message = docker_manager.create_network("jenkins-local-net")
        if success:
            console.print("[green]✓[/green] Network setup successful")
        else:
            console.print(f"[red]✗[/red] Network setup failed: {message}")

        # Create volume
        success, message = docker_manager.create_volume("jenkins-local-data")
        if success:
            console.print("[green]✓[/green] Volume setup successful")
        else:
            console.print(f"[red]✗[/red] Volume setup failed: {message}")

    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@docker.command()
@click.argument('action', type=click.Choice(['backup', 'restore']))
def volume(action):
    """Backup or restore Jenkins volume."""
    try:
        backup_path = Path(config_manager.get_config()["directories"]["volumes"]) / "jenkins-backup.tar.gz"
        
        if action == "backup":
            success, message = docker_manager.backup_volume("jenkins-local-data", backup_path)
            if success:
                console.print(f"[green]✓[/green] Volume backup created at {backup_path}")
            else:
                console.print(f"[red]✗[/red] Backup failed: {message}")
        else:
            success, message = docker_manager.restore_volume("jenkins-local-data", backup_path)
            if success:
                console.print(f"[green]✓[/green] Volume restored from {backup_path}")
            else:
                console.print(f"[red]✗[/red] Restore failed: {message}")

    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")


@cli.command()
@click.option(
    "--agents",
    default=1,
    help="Number of Jenkins agents to create",
    type=int
)
@click.option(
    "--memory",
    default="4g",
    help="Memory allocation for agents (e.g., 4g)",
    type=str
)
@click.option(
    "--cpus",
    default=2,
    help="Number of CPUs for agents",
    type=int
)
@click.option(
    "--admin-user",
    default="admin",
    help="Jenkins admin username",
    type=str
)
@click.option(
    "--admin-password",
    default="admin",
    help="Jenkins admin password",
    type=str
)
def setup(agents: int, memory: str, cpus: int, admin_user: str, admin_password: str):
    """Set up complete Jenkins infrastructure with specified configuration."""
    try:
        console.print("[bold blue]Starting complete Jenkins infrastructure setup...[/bold blue]")
        
        # Step 1: Initialize configuration
        console.print("\n[bold]Step 1/6: Initializing configuration...[/bold]")
        config_manager.init_directories()
        
        # Update configuration with CLI parameters
        config_manager.update_config({
            "agents": {
                "count": agents,
                "memory": memory,
                "cpus": cpus
            }
        })
        
        console.print("[green]✓[/green] Configuration initialized")
        console.print(f"Config directory: {config_manager.config['directories']['config']}")
        console.print("\n[bold]Infrastructure Configuration:[/bold]")
        console.print(f"Agents: {agents}")
        console.print(f"Memory: {memory}")
        console.print(f"CPUs: {cpus}")
        
        # Step 2: Initialize Docker resources
        console.print("\n[bold]Step 2/6: Setting up Docker resources...[/bold]")
        
        # Check Docker daemon
        if not docker_manager.check_docker_running():
            console.print("[bold red]Error: Docker daemon is not running[/bold red]")
            return
            
        # Create network
        success, message = docker_manager.create_network("jenkins-local-net")
        if success:
            console.print("[green]✓[/green] Network setup successful")
        else:
            console.print(f"[yellow]![/yellow] Network setup note: {message}")

        # Create volume
        success, message = docker_manager.create_volume("jenkins-local-data")
        if success:
            console.print("[green]✓[/green] Volume setup successful")
        else:
            console.print(f"[yellow]![/yellow] Volume setup note: {message}")
            
        # Step 3: Generate SSH keys
        console.print("\n[bold]Step 3/6: Setting up SSH keys...[/bold]")
        
        if ssh_manager.keys_exist():
            console.print("[green]✓[/green] SSH keys already exist")
        else:
            success, message = ssh_manager.generate_key_pair()
            if success:
                console.print("[green]✓[/green] SSH key pair generated successfully")
            else:
                console.print(f"[red]✗[/red] Failed to generate SSH keys: {message}")
                return
                
        # Step 4: Deploy Jenkins master
        console.print("\n[bold]Step 4/6: Deploying Jenkins master...[/bold]")
        
        # Deploy master
        success, message = jenkins_master.deploy()
        
        if not success:
            console.print(f"[red]✗[/red] Failed to deploy Jenkins master: {message}")
            return
            
        console.print("[green]✓[/green] Jenkins master deployed successfully")
        
        # Configure initial setup
        console.print("Configuring initial setup...")
        success, message = jenkins_master.configure_initial_setup(admin_user, admin_password)
        
        if not success:
            console.print(f"[red]✗[/red] Initial setup failed: {message}")
            return
            
        console.print("[green]✓[/green] Initial setup completed")
        
        # Step 5: Install required plugins
        console.print("\n[bold]Step 5/7: Installing required plugins...[/bold]")
        
        required_plugins = [
            "credentials",
            "credentials-binding",
            "ssh-credentials",
            "ssh-slaves",
            "ssh-agent",
            "ssh"
        ]
        
        success, message = jenkins_master.install_plugins(admin_user, admin_password, required_plugins)
        
        if success:
            console.print(f"[green]✓[/green] {message}")
        else:
            console.print(f"[red]✗[/red] {message}")
            console.print("[yellow]![/yellow] Continuing with setup despite plugin installation issues")
        
        # Step 6: Check and build agent image if needed
        console.print("\n[bold]Step 6/7: Checking Jenkins agent image...[/bold]")
        
        # Get the agent image name from config
        agent_image = agent_manager.image
        
        # Check if the image exists
        if docker_manager.check_image_exists(agent_image):
            console.print(f"[green]✓[/green] Jenkins agent image '{agent_image}' already exists")
        else:
            console.print(f"[yellow]![/yellow] Jenkins agent image '{agent_image}' not found, building it now...")
            
            # Get the package directory to find the Dockerfile
            package_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent.parent
            dockerfile_path = package_dir / "docker" / "agent" / "Dockerfile"
            
            if not dockerfile_path.exists():
                console.print(f"[red]✗[/red] Dockerfile not found at {dockerfile_path}")
                console.print("[red]✗[/red] Cannot build agent image, setup will likely fail")
            else:
                console.print(f"Building image from {dockerfile_path}...")
                success, message = docker_manager.build_image(dockerfile_path, agent_image)
                
                if success:
                    console.print(f"[green]✓[/green] Successfully built Jenkins agent image")
                else:
                    console.print(f"[red]✗[/red] Failed to build agent image: {message}")
                    console.print("[red]✗[/red] Agent deployment will likely fail")
            
        # Step 7: Deploy Jenkins agents
        console.print("\n[bold]Step 7/7: Deploying Jenkins agents...[/bold]")
        
        agent_manager.agent_configurator = JenkinsAgentConfigurator(
            agent_manager.jenkins_url,
            admin_user,
            admin_password
        )
        
        results = agent_manager.deploy_agents(agents, str(cpus), memory)
        
        success_count = len([r for r in results if not r.get('error')])
        if success_count == agents:
            console.print(f"[green]✓[/green] Successfully deployed {agents} agent(s)")
        else:
            console.print(f"[yellow]![/yellow] Deployed {success_count} out of {agents} agent(s)")
            
        for i, result in enumerate(results, 1):
            status = "[green]✓[/green]" if not result.get('error') else "[red]✗[/red]"
            message = result.get('error') if result.get('error') else f"Agent {result['agent_name']} deployed successfully"
            console.print(f"{status} Agent {i}: {message}")
            
        # Final summary
        display_logo()
        console.print("\n[bold green]Jenkins infrastructure setup complete![/bold green]")
        console.print(f"Access Jenkins at: http://localhost:{jenkins_master.host_port}")
        console.print(f"Username: {admin_user}")
        console.print(f"Password: {admin_password}")
        console.print("\nUse the following commands to manage your infrastructure:")
        console.print("  jenkins-local-init master status - Check Jenkins master status")
        console.print("  jenkins-local-init agent list - List all agents")
        console.print("  jenkins-local-init agent logs - View agent logs")
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@cli.command()
def status():
    """Check the status of Jenkins infrastructure."""
    try:
        config = config_manager.get_config()
        console.print("[bold blue]Jenkins Infrastructure Status[/bold blue]")
        console.print("\n[bold green]Directories:[/bold green]")
        for name, path in config["directories"].items():
            exists = Path(path).exists()
            status = "✓" if exists else "✗"
            color = "green" if exists else "red"
            console.print(f"{name}: {path} [{color}]{status}[/{color}]")
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

########################################################
# SSH Commands
########################################################

@cli.group()
def ssh():
    """Manage SSH keys for Jenkins agents."""
    pass

@ssh.command()
@click.option('--force', is_flag=True, help='Force regenerate keys even if they exist')
def generate(force):
    """Generate SSH key pair for Jenkins agents."""
    try:
        
        if ssh_manager.keys_exist() and not force:
            console.print("[yellow]SSH keys already exist.[/yellow]")
            console.print("Use --force to regenerate keys.")
            return
            
        if force and ssh_manager.keys_exist():
            success, message = ssh_manager.backup_keys()
            if success:
                console.print("[green]✓[/green] Existing keys backed up")
            else:
                console.print(f"[red]✗[/red] Failed to backup existing keys: {message}")
            return
        
        success, message = ssh_manager.generate_key_pair()
        
        if success:
            console.print("[green]✓[/green] SSH key pair generated successfully")
            console.print("\n[bold blue]Key Locations:[/bold blue]")
            console.print(f"Private key: {ssh_manager.get_private_key_path()}")
            console.print(f"Public key: {ssh_manager.get_private_key_path()}.pub")
            
            console.print("\n[bold blue]Public Key Content:[/bold blue]")
            console.print(ssh_manager.get_public_key())
        else:
            console.print(f"[red]✗[/red] Failed to generate SSH key pair: {message}")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@ssh.command()
def show():
    """Display the public key."""
    try:
        
        if not ssh_manager.keys_exist():
            console.print("[yellow]No SSH keys found.[/yellow]")
            console.print("Generate keys first using: jenkins-local-init ssh generate")
            return
            
        console.print("[bold blue]Public Key Content:[/bold blue]")
        console.print(ssh_manager.get_public_key())
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@ssh.command()
def backup():
    """Backup existing SSH keys."""
    try:
        
        success, message = ssh_manager.backup_keys()
        
        if success:
            console.print("[green]✓[/green] SSH keys backed up successfully")
        else:
            console.print(f"[red]✗[/red] {message}")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

########################################################
# JenkinsAgent Commands
########################################################

@cli.group()
def agent():
    """Manage Jenkins agent containers."""
    pass

@agent.command()
@click.option('--count', default=1, help='Number of agents to deploy')
@click.option('--cpu', default='2', help='CPU limit per agent (e.g., 2)')
@click.option('--memory', default='2g', help='Memory limit per agent (e.g., 2g)')
@click.option('--admin-user', default='admin', help='Jenkins admin username')
@click.option('--admin-password', default='admin', help='Jenkins admin password')
def deploy(count: int, cpu: str, memory: str, admin_user: str, admin_password: str):
    """Deploy Jenkins agent containers."""
    try:
        if not ssh_manager.keys_exist():
            console.print("[red]Error: SSH keys not found[/red]")
            console.print("Generate SSH keys first: jenkins-local-init ssh generate")
            return
        
        # Check if agent image exists
        agent_image = agent_manager.image
        if not docker_manager.check_image_exists(agent_image):
            console.print(f"[yellow]Warning: Jenkins agent image '{agent_image}' not found[/yellow]")
            console.print("Building the image now...")
            
            # Get the package directory to find the Dockerfile
            package_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent.parent
            dockerfile_path = package_dir / "docker" / "agent" / "Dockerfile"
            
            if not dockerfile_path.exists():
                console.print(f"[red]Error: Dockerfile not found at {dockerfile_path}[/red]")
                console.print("Cannot build agent image. Please check your installation.")
                return
            
            console.print(f"Building image from {dockerfile_path}...")
            success, message = docker_manager.build_image(dockerfile_path, agent_image)
            
            if not success:
                console.print(f"[red]Error: Failed to build agent image: {message}[/red]")
                return
                
            console.print(f"[green]✓[/green] Successfully built Jenkins agent image")
        
        console.print(f"[bold blue]Deploying {count} Jenkins agent(s)...[/bold blue]")
        
        agent_manager.agent_configurator = JenkinsAgentConfigurator(
            agent_manager.jenkins_url,
            admin_user,
            admin_password
        )
        
        results = agent_manager.deploy_agents(count, cpu, memory)
        
        # Update this line to check for errors instead of success
        success_count = len([r for r in results if not r.get('error')])
        if success_count == count:
            console.print(f"[green]✓[/green] Successfully deployed {count} agent(s)")
        else:
            console.print(f"[yellow]![/yellow] Deployed {success_count} out of {count} agent(s)")
            
        # Update this section to handle dictionary results
        for i, result in enumerate(results, 1):
            status = "[green]✓[/green]" if not result.get('error') else "[red]✗[/red]"
            message = result.get('error') if result.get('error') else f"Agent {result['agent_name']} deployed successfully"
            console.print(f"{status} Agent {i}: {message}")
            
            # Show logs for failed agents
            if result.get('error'):
                _, logs = agent_manager.get_agent_logs(i)
                console.print("\n[bold red]Agent Logs:[/bold red]")
                console.print(logs)
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        
@agent.command()
def logs():
    """Show logs for all agents."""
    try:
        agents = agent_manager.list_agents()
        
        if not agents:
            console.print("[yellow]No agents found[/yellow]")
            return
            
        for agent in agents:
            name = agent['name']
            index = int(name.split('-')[-1])
            success, logs = agent_manager.get_agent_logs(index)
            
            console.print(f"\n[bold blue]Logs for {name}:[/bold blue]")
            console.print(logs)
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@agent.command()
def list():
    """List all Jenkins agents."""
    try:
        agents = agent_manager.list_agents()
        
        if not agents:
            console.print("[yellow]No agents found[/yellow]")
            return
            
        console.print("[bold blue]Jenkins Agents:[/bold blue]")
        for agent in agents:
            status_color = "green" if "Up" in agent['status'] else "red"
            console.print(f"[{status_color}]{agent['name']}[/{status_color}]")
            console.print(f"  Status: {agent['status']}")
            console.print(f"  ID: {agent['id']}\n")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@agent.command()
@click.argument('index', type=int)
def remove(index: int):
    """Remove a specific agent from both Docker and Jenkins."""
    try:
        agent_name = f"jenkins-local-agent-{index}"
        console.print(f"[bold blue]Removing agent {agent_name}...[/bold blue]")
        
        success, message = agent_manager.remove_agent(index)
        
        # The detailed output is already handled by the agent_manager.remove_agent method
        # Just display the final status
        if success:
            console.print(f"[green]✓[/green] Successfully removed agent {index}")
        else:
            console.print(f"[red]✗[/red] Failed to remove agent {index}")
            console.print(f"Details: {message}")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@agent.command()
def remove_all():
    """Remove all Jenkins agents from both Docker and Jenkins."""
    try:
        # The detailed output is already handled by the agent_manager.remove_all_agents method
        results = agent_manager.remove_all_agents()
        
        # Just display a final summary if needed
        success_count = sum(1 for success, _ in results if success)
        if len(results) == 0:
            console.print("[yellow]No agents found to remove[/yellow]")
        elif success_count == len(results):
            # The success message is already printed by remove_all_agents
            pass
        else:
            # The partial success message is already printed by remove_all_agents
            pass
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")


if __name__ == "__main__":
    cli()