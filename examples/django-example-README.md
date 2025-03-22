# Django Example Application for Jenkins Local Init

This is a simple Django REST API application that demonstrates CI/CD pipeline integration with Jenkins Local Init. The application provides basic CRUD operations for a "Task" model.

## Project Structure

```
jenkins-local-init-django/
├── Dockerfile            # Container definition for the application
├── Jenkinsfile           # CI/CD pipeline definition
├── manage.py             # Django management script
├── requirements.txt      # Python dependencies
├── api/                  # Django app for REST API
└── django_app/           # Django project settings
```

## Prerequisites 

- [Jenkins Local Init](https://github.com/Siddartha-Kodaboina/jenkins-local-init) installed
- Jenkins running with Ngrok for public URL access
- Git installed
- GitHub account

## Setting Up CI/CD with Jenkins Local Init (alias jent)

### Step 1: Start Jenkins with Ngrok

First, make sure you have Jenkins Local Init installed and set up with Ngrok:

```bash
# Authenticate with Ngrok (required only once)
jnet ngrok auth YOUR_NGROK_AUTHTOKEN

# Start Jenkins with public URL access
jnet setup --agents 2 --public
```

Verify Jenkins is running and note the Ngrok public URL:

```bash
jnet ngrok status
# Example output: Public URL: https://abc123.ngrok.io
```

### Step 2: Clone This Repository

```bash
git clone https://github.com/Siddartha-Kodaboina/jenkins-local-init-django.git
cd jenkins-local-init-django
```

### Step 3: Create a Jenkins Pipeline

1. Open Jenkins in your browser (http://localhost:8080)
2. Log in with the credentials you specified during setup (default: admin/admin)
3. Click "New Item"
4. Enter a name for your pipeline (e.g., "django-example")
5. Select "Pipeline" and click "OK"
6. In the configuration page:
   - Select "Github Project" and paste your forked repository URL
   - Under "Build Triggers", select "GitHub hook trigger for GITScm polling"
   - Under "Pipeline", select "Pipeline script from SCM"
   - Select "Git" as the SCM
   - Enter the repository URL (your forked repository URL)
   - Specify the branch (e.g., "*/main")
   - Script Path: "Jenkinsfile"
7. Click "Save"

### Step 4: Configure GitHub Webhook

1. In your GitHub repository:
   - Go to Settings > Webhooks > Add webhook
   - Set Payload URL to `https://your-ngrok-url/github-webhook/` (replace with your actual Ngrok URL)
   - Content type: `application/json`
   - Select "Just the push event"
   - Click "Add webhook"

### Step 5: Test the CI/CD Pipeline

1. Make a change to any file in the repository
2. Commit and push the change:
   ```bash
   git add .
   git commit -m "Test CI/CD pipeline"
   git push
   ```
3. Go to Jenkins and watch the pipeline execute automatically

## Understanding the Jenkinsfile

The Jenkinsfile defines a pipeline with the following stages:

1. **Checkout**: Retrieves the code from the Git repository
2. **Build Docker Image**: Builds a Docker image for the application
3. **Run Tests**: Executes Django tests inside the Docker container
4. **Deploy**: Placeholder for deployment steps (in a real environment)

### Node Labels

The pipeline is configured to run on nodes with the `agent` label. Jenkins Local Init automatically assigns labels to nodes:

- **Master Node**: Labeled as `master`
- **Agent Nodes**: Labeled as `agent`

This allows you to control where your builds run. For example, the Jenkinsfile starts with:

```groovy
pipeline {
    agent { label 'agent' }
    // ...
}
```

This ensures the pipeline runs on agent nodes, preserving resources on the master node for orchestration.

## Running the Application Locally

If you want to run the application outside of the CI/CD pipeline:

```bash
# Build the Docker image
docker build -t django-example .

# Run the container
docker run -p 8000:8000 django-example

# Access the API at http://localhost:8000/api/tasks/
```

## API Endpoints

- `GET /api/tasks/` - List all tasks
- `POST /api/tasks/` - Create a new task
- `GET /api/tasks/{id}/` - Retrieve a specific task
- `PUT /api/tasks/{id}/` - Update a specific task
- `DELETE /api/tasks/{id}/` - Delete a specific task

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.