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
