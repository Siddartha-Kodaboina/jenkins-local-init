FROM jenkins/ssh-agent:latest-jdk17

USER root

# Install required packages
RUN apt-get update && \
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        sudo && \
    # Verify Java installation
    java -version && \
    # Install Docker CLI
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce-cli docker-buildx-plugin && \
    rm -rf /var/lib/apt/lists/* && \
    # Add jenkins user to daemon group (GID 1) for Docker socket access
    usermod -aG daemon jenkins && \
    # Allow jenkins to use sudo without password for specific commands
    echo "jenkins ALL=(ALL) NOPASSWD: /usr/bin/chmod, /usr/sbin/sshd, /bin/mkdir, /bin/chmod" >> /etc/sudoers && \
    # Fix permissions and generate SSH host keys
    mkdir -p /etc/ssh /run/sshd && \
    ssh-keygen -A && \
    chown -R jenkins:jenkins /etc/ssh && \
    chmod 755 /run/sshd && \
    chown root:root /run/sshd && \
    # Fix environment file permissions
    touch /etc/environment && \
    chown jenkins:jenkins /etc/environment && \
    chmod 644 /etc/environment

# Create required directories with correct permissions
RUN mkdir -p /home/jenkins/.ssh && \
    chown -R jenkins:jenkins /home/jenkins/.ssh && \
    chmod 700 /home/jenkins/.ssh

# Copy and set up the startup script
COPY setup-and-run.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/setup-and-run.sh

USER jenkins

ENTRYPOINT ["/usr/local/bin/setup-and-run.sh"]