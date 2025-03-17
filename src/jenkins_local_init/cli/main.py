import click
from rich.console import Console
from rich.traceback import install
from ..config.manager import ConfigManager
from pathlib import Path
from ..core.docker import DockerManager
from ..core.jenkins import JenkinsMaster
# Install rich traceback handling
install()
console = Console()
config_manager = ConfigManager()
docker_manager = DockerManager()
jenkins_master = JenkinsMaster(docker_manager, config_manager)

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Jenkins Local Init - Set up Jenkins infrastructure locally on macOS."""
    pass
  
@cli.group()
def master():
    """Manage Jenkins master container."""
    pass

@master.command()
@click.option('--port', type=int, help='Custom port for Jenkins web interface')
@click.option('--jnlp-port', type=int, help='Custom port for JNLP agents')
def deploy(port, jnlp_port):
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
            console.print("\n[bold blue]Waiting for initial admin password...[/bold blue]")
            
            # Get initial admin password
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
def setup(agents: int, memory: str, cpus: int):
    """Set up Jenkins infrastructure with specified configuration."""
    try:
        # Initialize configuration
        config_manager.init_directories()
        
        # Update configuration with CLI parameters
        config_manager.update_config({
            "agents": {
                "count": agents,
                "memory": memory,
                "cpus": cpus
            }
        })
        
        console.print("[bold green]Configuration initialized[/bold green]")
        console.print(f"Config directory: {config_manager.config['directories']['config']}")
        console.print("\n[bold blue]Infrastructure Configuration:[/bold blue]")
        console.print(f"Agents: {agents}")
        console.print(f"Memory: {memory}")
        console.print(f"CPUs: {cpus}")
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

if __name__ == "__main__":
    cli()