import requests
import json
from typing import Tuple, Optional
from pathlib import Path
import time
import base64

class JenkinsAgentConfigurator:
    def __init__(self, jenkins_url: str, username: str, password: str):
        self.jenkins_url = jenkins_url
        self.username = username
        self.password = password
        self.crumb = None
        self.session = requests.Session()
        self.session.auth = (username, password)
    
    def _get_crumb(self) -> Optional[dict]:
        """Get Jenkins crumb for CSRF protection."""
        try:
            response = self.session.get(
                f"{self.jenkins_url}/crumbIssuer/api/json",
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting crumb: {str(e)}")
        return None

    def _get_headers(self) -> dict:
        """Get headers for Jenkins API requests."""
        headers = {'Content-Type': 'application/json'}
        if not self.crumb:
            crumb_data = self._get_crumb()
            if crumb_data:
                self.crumb = {crumb_data.get('crumbRequestField'): crumb_data.get('crumb')}
                headers.update(self.crumb)
        return headers

    def configure_credentials(self, private_key_path: Path) -> Tuple[bool, str]:
        """Configure SSH credentials in Jenkins master."""
        try:
            session = requests.Session()
            session.auth = (self.username, self.password)

            # First verify if credentials already exist
            verify_url = f"{self.jenkins_url}/manage/credentials/store/system/domain/_/api/json?tree=credentials[id]"
            verify_response = session.get(verify_url)
            if verify_response.status_code == 200:
                existing_creds = verify_response.json()
                # Check if credentials already exist
                if any(cred.get("id") == "jenkins-agent-ssh-key" for cred in existing_creds.get("credentials", [])):
                    print("✓ SSH credentials already exist")
                    return True, "Credentials already exist"
            
            # Read private key
            with open(private_key_path, 'r') as f:
                private_key = f.read()

            # Get crumb
            crumb_response = session.get(f"{self.jenkins_url}/crumbIssuer/api/json")
            if crumb_response.status_code != 200:
                return False, f"Failed to get crumb: {crumb_response.text[:200]}"
            
            crumb_data = crumb_response.json()

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                crumb_data['crumbRequestField']: crumb_data['crumb']
            }

            form_data = {
                'json': json.dumps({
                    "": "0",
                    "credentials": {
                        "scope": "GLOBAL",
                        "id": "jenkins-agent-ssh-key",
                        "username": "jenkins",
                        "description": "SSH key for Jenkins agent",
                        "privateKeySource": {
                            "value": "0",
                            "privateKey": private_key,
                            "stapler-class": "com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey$DirectEntryPrivateKeySource"
                        },
                        "stapler-class": "com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey",
                        "$class": "com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey"
                    }
                }),
                'Submit': 'OK'
            }

            create_url = f"{self.jenkins_url}/manage/credentials/store/system/domain/_/createCredentials"

            response = session.post(
                create_url,
                headers=headers,
                data=form_data
            )


            # Verify creation
            verify_response = session.get(verify_url)
            if verify_response.status_code == 200:
                after_creds = verify_response.json()
                
                # Verify the credentials were actually created
                if any(cred.get("id") == "jenkins-agent-ssh-key" for cred in after_creds.get("credentials", [])):
                    return True, "Credentials configured successfully"
                else:
                    return False, "Credentials not found after creation attempt"

            if response.status_code in [200, 201, 302]:
                if 'html' in response.headers.get('Content-Type', ''):
                    return False, "Got HTML response instead of credential creation confirmation"
                return True, "Credentials configured successfully"
            
            return False, f"Failed to configure credentials: {response.text[:200]}"

        except Exception as e:
            return False, f"Failed to configure credentials: {str(e)}"

    def configure_agent(self, agent_name: str, host: str = "jenkins-local-agent-1", port: int = 22) -> Tuple[bool, str]:
        """Configure Jenkins agent using SSH."""
        try:
            session = requests.Session()
            session.auth = (self.username, self.password)

            # Get cookie first
            cookie_response = session.get(f"{self.jenkins_url}/computer/new")
            if cookie_response.status_code != 200:
                return False, "Failed to get cookie"
            
            cookie = cookie_response.cookies.get_dict()

            # Get crumb using cookie
            crumb_response = session.get(
                f"{self.jenkins_url}/crumbIssuer/api/json",
                cookies=cookie
            )
            if crumb_response.status_code != 200:
                return False, f"Failed to get crumb: {crumb_response.text[:200]}"
            
            crumb_data = crumb_response.json()
            crumb = crumb_data['crumb']

            # Prepare the JSON payload for SSH launcher
            json_data = {
                "name": agent_name,
                "nodeDescription": "",
                "numExecutors": "1",
                "remoteFS": "/home/jenkins",
                "labelString": "",
                "mode": "NORMAL",
                "": ["hudson.plugins.sshslaves.SSHLauncher", "0"],
                "launcher": {
                    "stapler-class": "hudson.plugins.sshslaves.SSHLauncher",
                    "$class": "hudson.plugins.sshslaves.SSHLauncher",
                    "host": host,
                    "port": port,
                    "credentialsId": "jenkins-agent-ssh-key",
                    "launchTimeoutSeconds": "60",
                    "maxNumRetries": "10",
                    "retryWaitTime": "15",
                    "sshHostKeyVerificationStrategy": {
                        "stapler-class": "hudson.plugins.sshslaves.verifiers.NonVerifyingKeyVerificationStrategy",
                        "$class": "hudson.plugins.sshslaves.verifiers.NonVerifyingKeyVerificationStrategy"
                    }
                },
                "retentionStrategy": {
                    "stapler-class": "hudson.slaves.RetentionStrategy$Always",
                    "$class": "hudson.slaves.RetentionStrategy$Always"
                },
                "nodeProperties": {"stapler-class-bag": "true"},
                "type": "hudson.slaves.DumbSlave",
                "Submit": "",
                "Jenkins-Crumb": crumb
            }

            # Prepare form data
            form_data = {
                "name": agent_name,
                "nodeDescription": "",
                "_.numExecutors": "1",
                "_.remoteFS": "/home/jenkins",
                "_.labelString": "",
                "mode": "NORMAL",
                "stapler-class": [
                    "hudson.plugins.sshslaves.SSHLauncher",
                    "hudson.slaves.RetentionStrategy$Always",
                    "hudson.slaves.SimpleScheduledRetentionStrategy",
                    "hudson.slaves.RetentionStrategy$Demand"
                ],
                "$class": [
                    "hudson.plugins.sshslaves.SSHLauncher",
                    "hudson.slaves.RetentionStrategy$Always",
                    "hudson.slaves.SimpleScheduledRetentionStrategy",
                    "hudson.slaves.RetentionStrategy$Demand"
                ],
                "_.host": host,
                "_.port": str(port),
                "_.credentialsId": "jenkins-agent-ssh-key",
                "_.launchTimeoutSeconds": "60",
                "_.maxNumRetries": "10",
                "_.retryWaitTime": "15",
                "_.sshHostKeyVerificationStrategy": "0",
                "stapler-class-sshHostKeyVerificationStrategy": "hudson.plugins.sshslaves.verifiers.NonVerifyingKeyVerificationStrategy",
                "stapler-class-bag": "true",
                "_.freeDiskSpaceThreshold": "1GiB",
                "_.freeDiskSpaceWarningThreshold": "2GiB",
                "_.freeTempSpaceThreshold": "1GiB",
                "_.freeTempSpaceWarningThreshold": "2GiB",
                "type": "hudson.slaves.DumbSlave",
                "Submit": "",
                "json": json.dumps(json_data)
            }

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                crumb_data['crumbRequestField']: crumb
            }

            response = session.post(
                f"{self.jenkins_url}/computer/doCreateItem",
                headers=headers,
                data=form_data,
                cookies=cookie
            )

            if response.status_code in [200, 302]:
                return True, "Agent configured successfully"
            return False, f"Failed to configure agent: {response.text[:200]}"

        except Exception as e:
            print(f"✗ Exception during agent configuration: {str(e)}")
            return False, f"Failed to configure agent: {str(e)}"
