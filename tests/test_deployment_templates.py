from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_systemd_template_uses_a_single_loopback_worker():
    content = (PROJECT_ROOT / "deploy/systemd/asset-lifecycle.service").read_text(
        encoding="utf-8"
    )

    assert "User=asset-lifecycle" in content
    assert "EnvironmentFile=/etc/asset-lifecycle/asset-lifecycle.env" in content
    assert "--host 127.0.0.1" in content
    assert "--port 8000" in content
    assert "--workers 1" in content


def test_nginx_template_is_the_public_http_entry_point():
    content = (PROJECT_ROOT / "deploy/nginx/asset-lifecycle.conf").read_text(
        encoding="utf-8"
    )

    assert "listen 80;" in content
    assert "proxy_pass http://127.0.0.1:8000;" in content
    assert "client_max_body_size 10m;" in content


def test_deployment_readme_requires_https_before_formal_public_use():
    content = (PROJECT_ROOT / "deploy/README.md").read_text(encoding="utf-8")

    assert "HTTPS" in content
    assert "HTTP" in content
    assert "127.0.0.1:8000" in content


def test_backup_timer_uses_the_application_user_and_daily_schedule():
    service = (
        PROJECT_ROOT / "deploy/systemd/asset-lifecycle-backup.service"
    ).read_text(encoding="utf-8")
    timer = (
        PROJECT_ROOT / "deploy/systemd/asset-lifecycle-backup.timer"
    ).read_text(encoding="utf-8")

    assert "User=asset-lifecycle" in service
    assert "scripts.backup_database" in service
    assert "--retention 14" in service
    assert "OnCalendar=*-*-* 02:30:00" in timer


def test_healthcheck_timer_runs_a_local_check_every_minute():
    service = (
        PROJECT_ROOT / "deploy/systemd/asset-lifecycle-healthcheck.service"
    ).read_text(encoding="utf-8")
    timer = (
        PROJECT_ROOT / "deploy/systemd/asset-lifecycle-healthcheck.timer"
    ).read_text(encoding="utf-8")

    assert "scripts.healthcheck" in service
    assert "127.0.0.1:8000/api/health" in service
    assert "--minimum-free-mib 1024" in service
    assert "OnUnitActiveSec=1min" in timer


def test_ci_runs_the_complete_pytest_release_gate():
    workflow = (PROJECT_ROOT / ".github/workflows/ci-cd.yml").read_text(
        encoding="utf-8"
    )

    assert "python -m pip install pytest httpx" in workflow
    assert "python -m pytest -q --disable-warnings" in workflow


def test_ci_deploys_only_from_main():
    workflow = (PROJECT_ROOT / ".github/workflows/ci-cd.yml").read_text(
        encoding="utf-8"
    )

    assert "      - main" in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow


def test_ci_builds_frontend_v2_production_before_packaging():
    workflow = (PROJECT_ROOT / ".github/workflows/ci-cd.yml").read_text(
        encoding="utf-8"
    )

    assert "actions/setup-node@v4" in workflow
    assert 'node-version: "20"' in workflow
    assert "working-directory: frontend-v2" in workflow
    assert "npm ci" in workflow
    assert "npm run typecheck" in workflow
    assert "npm run test:unit" in workflow
    assert "npm run build" in workflow
    assert "npm run build:preview" not in workflow
    assert workflow.index("npm run build") < workflow.index("Package release")


def test_release_package_excludes_frontend_v2_build_dependencies():
    workflow = (PROJECT_ROOT / ".github/workflows/ci-cd.yml").read_text(
        encoding="utf-8"
    )

    assert "--exclude='frontend-v2/node_modules'" in workflow
    assert "--exclude='frontend-v2/test-results'" in workflow
    assert "--exclude='frontend-v2/dist-preview'" in workflow
    assert "--exclude='frontend-v2/*.timestamp-*.mjs'" in workflow


def test_backend_serves_frontend_v2_dist_as_root_and_keeps_legacy_rollback():
    content = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert 'frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")' in content
    assert (
        'frontend_v2_dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend-v2", "dist")'
        in content
    )
    assert 'app.mount("/static", StaticFiles(directory=frontend_dir), name="static")' in content
    assert 'app.mount("/legacy", StaticFiles(directory=frontend_dir, html=True), name="frontend-legacy")' in content
    assert 'app.mount("/assets", StaticFiles(directory=frontend_v2_assets_dir), name="frontend-v2-assets")' in content
    assert 'index_path = os.path.join(frontend_v2_dist_dir, "index.html")' in content


def test_release_script_requires_explicit_scenario_data_opt_in():
    script = (PROJECT_ROOT / "deploy/github-actions-deploy.sh").read_text(
        encoding="utf-8"
    )

    assert 'SEED_SCENARIO_TEST_DATA="${SEED_SCENARIO_TEST_DATA:-false}"' in script
    assert 'if [ "$SEED_SCENARIO_TEST_DATA" = "true" ] && [ -f "$NEW_DIR/generate_scenario_test_data.py" ]; then' in script


def test_release_script_restarts_service_after_switching_release_directory():
    script = (PROJECT_ROOT / "deploy/github-actions-deploy.sh").read_text(
        encoding="utf-8"
    )

    assert 'mv "$NEW_DIR" "$APP_DIR"' in script
    assert "systemctl enable asset-lifecycle" in script
    assert "systemctl restart asset-lifecycle" in script
    assert script.index('mv "$NEW_DIR" "$APP_DIR"') < script.index(
        "systemctl restart asset-lifecycle"
    )
