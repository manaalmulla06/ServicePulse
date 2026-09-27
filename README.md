# ServicePulse – Web Service Health Monitoring Dashboard

ServicePulse is a Flask-based web application used to monitor the health and response time of web services.

A user can register a service by entering its name, URL, and acceptable response-time threshold. ServicePulse checks the registered services and displays whether each service is **UP, SLOW, or DOWN**.

The project also includes automated testing, code linting, GitHub Actions CI/CD, and deployment on Render.

---

## 1. What the Project Does

ServicePulse allows a user to:

* Add a web service to monitor
* Set a response-time threshold
* Check the service immediately after adding it
* View the current service status
* Check response time and HTTP status code
* Manually check a service again
* Edit service details
* Delete a service
* View the check history of a service
* Access service information through a JSON API
* Check the application health through `/health`

The application classifies services as:

| Status | Condition                                                          |
| ------ | ------------------------------------------------------------------ |
| UP     | HTTP response is 200–399 and response time is within the threshold |
| SLOW   | HTTP response is 200–399 but response time is above the threshold  |
| DOWN   | HTTP response is 400+ or the request fails                         |

---

## 2. Technologies Used

### Backend

* Python 3.12
* Flask
* SQLite
* Requests

### Frontend

* HTML
* CSS
* Jinja2 templates

### Testing and Code Quality

* Pytest
* Flake8

### Version Control and CI/CD

* Git
* GitHub
* GitHub Actions

### Deployment

* Render
* Gunicorn

No JavaScript or Docker is used in this project.

---

## 3. Project Structure


### Important files

**app.py**

Contains the Flask application, database operations, service monitoring logic, routes, validation, API, and health endpoint.

**dashboard.html**

Displays the registered services and their latest monitoring results.

**history.html**

Displays the monitoring history for a selected service.

**edit.html**

Allows the user to modify the name, URL, and response-time threshold of a service.

**style.css**

Contains the styling of the application.

**test_app.py**

Contains automated tests for the Flask application.

**ci-cd.yml**

Contains the GitHub Actions workflow used for testing and deployment.

**requirements.txt**

Contains the Python packages required to run the application.

---

# 4. How Service Monitoring Works

When a service is added, ServicePulse stores its details in the SQLite database.

The application then sends an HTTP request to the service using the Python `requests` library.

The response time is calculated using `time.perf_counter()`.

The application checks:

1. Whether the request was successful.
2. The HTTP status code.
3. How long the request took.
4. The response-time threshold configured for that service.

For example:

```text
Threshold = 1000 ms

Response:
HTTP 200
Response Time = 450 ms

Result = UP
```

If the same service takes:

```text
HTTP 200
Response Time = 1500 ms

Result = SLOW
```

If the request fails or returns an HTTP error:

```text
Connection Error

Result = DOWN
```

Every check is stored in the `checks` table so that previous results can be viewed later.

---

# 5. Automatic Checking

ServicePulse does not run a separate background monitoring server.

Instead, the dashboard automatically refreshes every 30 seconds.

When the dashboard is loaded, Flask checks the registered services and stores their latest results.

The monitoring therefore works while the dashboard is open.

A user can also manually check a service using the **Check Now** option.

---

# 6. Database

SQLite is used because the project is small and does not require a separate database server.

There are two main tables.

### services

Stores the services registered by the user.

```text
id
name
url
threshold
created_at
```

### checks

Stores the results of service checks.

```text
id
service_id
status
status_code
response_time
threshold
checked_at
error_message
```

The `service_id` connects each check with its corresponding service.

---

# 7. API

ServicePulse provides a JSON API at:

```text
/api/services
```

This endpoint returns the registered services along with their latest monitoring information.

Example:

```json
[
    {
        "id": 1,
        "name": "Google",
        "url": "https://www.google.com",
        "threshold": 1000,
        "status": "UP",
        "status_code": 200,
        "response_time": 245.32,
        "checked_at": "2026-09-27 10:30:20"
    }
]
```

The API can be used by another application to obtain the current monitoring data.

---

# 8. Health Endpoint

The application provides a simple health endpoint:

```text
/health
```

It returns JSON containing the application status and running commit ID.

Example:

```json
{
    "status": "healthy",
    "commit": "6fb34a3"
}
```

This endpoint is useful for checking whether the deployed application is running correctly.

---

# 9. Git Workflow

Git is used to maintain the project history and separate development work.

The project uses a feature-branch approach.

The general workflow is:

```text
Create Feature Branch
        ↓
Make Changes
        ↓
Commit Changes
        ↓
Push Branch to GitHub
        ↓
Create Pull Request
        ↓
GitHub Actions Runs Tests
        ↓
Merge into main
```

For example, the CI/CD work was developed using:

```text
feature/ci-cd
```

and the Render deployment changes were developed using:

```text
feature/render-deployment
```

After checking the changes, the branches were merged into `main`.

---

# 10. GitHub Actions CI/CD Workflow

The CI/CD pipeline is defined in:

```text
.github/workflows/ci-cd.yml
```

The workflow performs two main jobs:

```text
             GitHub Push
                  │
                  ▼
             ┌─────────┐
             │   Test  │
             └─────────┘
                  │
          ┌───────┴────────┐
          ▼                ▼
       Flake8            Pytest
          │                │
          └───────┬────────┘
                  ▼
             Tests Pass
                  │
                  ▼
             ┌─────────┐
             │ Deploy  │
             └─────────┘
                  │
                  ▼
           Render Deploy Hook
                  │
                  ▼
               Render
```

---

## 11. Test Job

The first job is called `test`.

It runs on an Ubuntu GitHub Actions runner.

The workflow:

1. Checks out the repository.
2. Installs Python 3.12.
3. Installs the packages from `requirements.txt`.
4. Runs Flake8.
5. Runs Pytest.

The relevant commands are:

```bash
python -m flake8 --max-line-length=120 --exclude=venv,.venv .
```

and:

```bash
python -m pytest -v
```

If either linting or testing fails, the workflow stops.

---

# 12. Deployment Job

The deployment job depends on the test job.

This is controlled using:

```yaml
needs: test
```

Therefore, deployment cannot happen if the test job fails.

Deployment also runs only when code is pushed to the `main` branch.

```yaml
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

This prevents a feature-branch test from automatically deploying the application.

---

# 13. Render Deployment

The Flask application is deployed on Render.

The Render service uses:

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
gunicorn app:app
```

Render Auto-Deploy is disabled.

Instead, GitHub Actions sends a request to the Render Deploy Hook after the tests have passed.

The Deploy Hook is stored in GitHub as a repository secret:

```text
RENDER_DEPLOY_HOOK
```

The actual URL is not stored directly in the workflow file.

This prevents the deployment URL from being exposed in the public repository.

---

# 14. Why Auto-Deploy is Disabled

Auto-Deploy is disabled so that deployment is controlled by the GitHub Actions pipeline.

The sequence is:

```text
Code pushed to main
        ↓
GitHub Actions
        ↓
Flake8
        ↓
Pytest
        ↓
If everything passes
        ↓
Render Deploy Hook
        ↓
Application deployed
```

This ensures that the application is not deployed before the automated checks have completed successfully.

---

# 15. Commit ID in the Application

The application displays the running Git commit ID.

On Render, the application reads:

```text
RENDER_GIT_COMMIT
```

The commit ID is shortened to the first seven characters.

This makes it possible to identify which version of the source code is currently running.

For example:

```text
Commit: 6fb34a3
```

This is also useful when demonstrating CI/CD because the deployed version can be compared with the commit that triggered the workflow.

---

# 16. Testing

The project currently contains automated tests for:

### Health endpoint

Checks whether:

```text
/health
```

returns HTTP 200 and the expected JSON response.

### Adding a service

Checks whether a valid service can be added successfully.

### Invalid service input

Checks that invalid input is rejected.

### API

Checks whether:

```text
/api/services
```

returns a valid JSON list.

The tests can be run locally using:

```bash
python -m pytest -v
```

---

# 17. Running the Project Locally

Clone the repository:

```bash
git clone https://github.com/manaalmulla06/ServicePulse.git
```

Move into the project folder:

```bash
cd ServicePulse
```

Install the required packages:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python app.py
```

The application will normally be available at:

```text
http://127.0.0.1:5000
```

---

# 18. Running Tests Locally

Run:

```bash
python -m pytest -v
```

For code quality checking:

```bash
python -m flake8 --max-line-length=120 --exclude=venv,.venv .
```

Both checks should pass before pushing changes to GitHub.

---

# 19. Failure Handling in CI/CD

One of the important parts of the project is that deployment depends on successful testing.

For example:

```text
Test fails
   ↓
Test job = FAILED
   ↓
Deploy job does not run
   ↓
No deployment
```

When the test is fixed:

```text
Test passes
   ↓
Deploy job runs
   ↓
Render deployment starts
```

This prevents a known failing version from being automatically deployed.

---

# 20. Live Application

The application is deployed on Render and can be accessed using its Render URL.

The deployed application provides:

* Service monitoring dashboard
* Service management
* Monitoring history
* JSON API
* Health endpoint
* Commit ID information

---

# 21. Future Improvements

Some possible improvements for a larger version of ServicePulse would be:

* User authentication
* Email or notification alerts
* Uptime percentage calculation
* Response-time graphs
* Scheduled background monitoring
* PostgreSQL instead of SQLite
* Multiple monitoring locations
* Incident tracking
* Service groups
* Role-based access

These features were kept outside the current version so that the project remains focused on the core monitoring and CI/CD requirements.

---

## 22. Summary

ServicePulse combines a simple Flask monitoring application with software development and deployment practices.

The application handles service monitoring and stores the results in SQLite. Pytest is used for automated testing and Flake8 is used for code quality checks. GitHub is used for version control and pull requests.

The GitHub Actions workflow first runs the tests and linting. Only after the test job succeeds can the deployment job run. The deployment job uses a Render Deploy Hook to deploy the latest version to the live application.

This gives the project a complete development flow:

```text
Development
     ↓
Git Feature Branch
     ↓
Pull Request
     ↓
Automated Testing
     ↓
Merge to main
     ↓
GitHub Actions
     ↓
Flake8 + Pytest
     ↓
Render Deploy Hook
     ↓
Live Application
```
