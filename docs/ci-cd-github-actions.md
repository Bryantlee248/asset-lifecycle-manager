# GitHub + GitHub Actions CI/CD

## What this does

- Push to `main` runs CI.
- CI installs dependencies, compiles `backend`, imports the FastAPI app, and runs the complete `pytest` suite.
- If CI passes, GitHub Actions packages the repo and uploads it to the target server over SSH.
- The server script backs up SQLite, deploys a fresh release to `/opt/asset-lifecycle-manager`, restarts the systemd service, and verifies the public homepage.
- If startup fails, the server rolls back to the previous release.

Scenario test data is disabled during deployment by default. Only an explicit `SEED_SCENARIO_TEST_DATA=true` value on the server-side deployment command can run `generate_scenario_test_data.py`; the GitHub Actions workflow does not set that value.

## GitHub Secrets you must add

- `DEPLOY_HOST` = `125.77.25.229`
- `DEPLOY_USER` = `root`
- `DEPLOY_PORT` = `22`
- `DEPLOY_SSH_KEY` = the private key allowed to SSH to the server
- `PUBLIC_URL` = `http://125.77.25.229:8081`

## How to use it

1. Commit and push to `main`.
2. Watch the `ci-cd` workflow in GitHub Actions.
3. If CI passes, deployment runs automatically.

## What you should change later

- Replace the root SSH deployment with a dedicated deploy user if you want stricter server access control.
- Add HTTPS and a real domain when you are ready for production use.
