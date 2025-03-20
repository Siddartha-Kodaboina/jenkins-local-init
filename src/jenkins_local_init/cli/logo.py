"""
JNET logo display module.
"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Jenkins colors
JENKINS_BLUE = "#335061"
JENKINS_GREEN = "#81B0C4"
JENKINS_LIGHT_BLUE = "#6D7F8B"

def get_logo():
    """Return the JNET logo as a Rich Text object."""
    logo = """
     ██╗███╗   ██╗███████╗████████╗
     ██║████╗  ██║██╔════╝╚══██╔══╝
     ██║██╔██╗ ██║█████╗     ██║   
██   ██║██║╚██╗██║██╔══╝     ██║   
╚█████╔╝██║ ╚████║███████╗   ██║   
 ╚════╝ ╚═╝  ╚═══╝╚══════╝   ╚═╝   
                                    
    """
    
    # Create a Text object with the logo
    text_logo = Text(logo)
    text_logo.stylize(f"bold {JENKINS_BLUE}")
    
    # Add a subtitle with Jenkins green
    subtitle = Text("\n Jenkins Network - Distributed Infrastructure Tool ", style=f"bold {JENKINS_GREEN}")
    
    # Combine logo and subtitle
    full_logo = Text.assemble(text_logo, subtitle)
    
    return full_logo

def display_logo():
    """Display the JNET logo."""
    console = Console()
    logo = get_logo()
    
    # Create a panel with the logo
    panel = Panel(
        logo,
        border_style=JENKINS_LIGHT_BLUE,
        padding=(1, 2),
    )
    
    console.print(panel)

if __name__ == "__main__":
    display_logo()
