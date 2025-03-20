#!/bin/bash

# Write the SSH key if provided
if [[ -n "$JENKINS_AGENT_SSH_PUBKEY" ]]; then
    echo "$JENKINS_AGENT_SSH_PUBKEY" > /home/jenkins/.ssh/authorized_keys
    chmod 600 /home/jenkins/.ssh/authorized_keys
fi

# Ensure Docker socket has correct permissions if mounted
if [ -e /var/run/docker.sock ]; then
    sudo chmod 666 /var/run/docker.sock
    # Verify docker access
    if ! docker info >/dev/null 2>&1; then
        echo "Warning: Docker socket access failed"
    else
        echo "Docker socket access verified"
    fi
fi

# Start SSHD with sudo
exec sudo /usr/sbin/sshd -D -e