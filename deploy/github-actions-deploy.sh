#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="asset-lifecycle"
APP_DIR="/opt/asset-lifecycle-manager"
DATA_DIR="/data/asset-lifecycle-manager"
BACKUP_ROOT="/root/deploy-backups/asset-lifecycle-manager"
ENV_FILE="/etc/asset-lifecycle/asset-lifecycle.env"
ARCHIVE="/tmp/asset-lifecycle-manager.tgz"
PUBLIC_URL="${PUBLIC_URL:-http://125.77.25.229:8081}"
SOURCE_SHA="${SOURCE_SHA:-unknown}"
RELEASE_ID="$(date +%Y%m%d-%H%M%S)"
RELEASE_BACKUP_DIR="${BACKUP_ROOT}/opt-release-${RELEASE_ID}"
NEW_DIR="${APP_DIR}.new"

cleanup() {
  rm -rf "${NEW_DIR:?}" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$DATA_DIR" "$DATA_DIR/backups" "$BACKUP_ROOT"
chmod 700 "$DATA_DIR/backups" "$BACKUP_ROOT"

if ! id -u asset-lifecycle >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin asset-lifecycle
fi

mkdir -p "$(dirname "$ENV_FILE")"
chmod 700 "$(dirname "$ENV_FILE")"
if [ ! -f "$ENV_FILE" ]; then
  python3 <<'PY' > /etc/asset-lifecycle/asset-lifecycle.env
import secrets
print('ENV=production')
print('JWT_SECRET_KEY=' + secrets.token_hex(32))
print('DEFAULT_ADMIN_PASSWORD=' + secrets.token_urlsafe(18))
print('DATABASE_URL=sqlite:////opt/asset-lifecycle-manager/asset_lifecycle.db')
print('CORS_ORIGINS=http://125.77.25.229:8081')
PY
  chmod 600 "$ENV_FILE"
fi

if [ -f "$DATA_DIR/asset_lifecycle.db" ]; then
  python3 <<'PY'
from pathlib import Path
import sqlite3, datetime
src = Path('/data/asset-lifecycle-manager/asset_lifecycle.db')
dst = Path('/data/asset-lifecycle-manager/backups') / (
    'asset_lifecycle-pre-release-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.db'
)
with sqlite3.connect(src) as source, sqlite3.connect(dst) as target:
    source.backup(target)
with sqlite3.connect(src) as conn:
    result = conn.execute('PRAGMA integrity_check').fetchone()[0]
    if result != 'ok':
        raise SystemExit(f'integrity_check={result}')
print(f'backup={dst}')
PY
fi

rm -rf "$NEW_DIR"
mkdir -p "$NEW_DIR"
tar -xzf "$ARCHIVE" -C "$NEW_DIR"

if [ ! -x "$NEW_DIR/.venv/bin/python" ]; then
  python3 -m venv "$NEW_DIR/.venv"
fi

"$NEW_DIR/.venv/bin/python" -m pip install --upgrade pip
"$NEW_DIR/.venv/bin/python" -m pip install -i "${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" -r "$NEW_DIR/requirements.txt"

ln -sfn "$DATA_DIR/asset_lifecycle.db" "$NEW_DIR/asset_lifecycle.db"

if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

export ENV=production
export DATABASE_URL="${DATABASE_URL:-sqlite:////opt/asset-lifecycle-manager/asset_lifecycle.db}"
export CORS_ORIGINS="${CORS_ORIGINS:-$PUBLIC_URL}"

cd "$NEW_DIR"
"$NEW_DIR/.venv/bin/python" - <<'PY'
import sys
sys.path.insert(0, 'backend')
import main
print(f'import_ok={main.app.title}')
PY

printf 'source_path=%s\nsource_sha=%s\ndeployed_at=%s\npublic_url=%s\n' \
  "$PWD" "$SOURCE_SHA" "$(date -Is)" "$PUBLIC_URL" > "$NEW_DIR/.release-info"

chown -R asset-lifecycle:asset-lifecycle "$NEW_DIR"

cat > /etc/systemd/system/asset-lifecycle.service <<'UNIT'
[Unit]
Description=IT Asset Lifecycle Manager
After=network.target

[Service]
Type=simple
User=asset-lifecycle
Group=asset-lifecycle
WorkingDirectory=/opt/asset-lifecycle-manager
EnvironmentFile=-/etc/asset-lifecycle/asset-lifecycle.env
Environment=ENV=production
Environment=DATABASE_URL=sqlite:////opt/asset-lifecycle-manager/asset_lifecycle.db
ExecStart=/opt/asset-lifecycle-manager/.venv/bin/python -m uvicorn main:app --app-dir /opt/asset-lifecycle-manager/backend --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload

if [ -d "$APP_DIR" ]; then
  mkdir -p "$RELEASE_BACKUP_DIR"
  cp -a /etc/systemd/system/asset-lifecycle.service "$RELEASE_BACKUP_DIR/asset-lifecycle.service.before" 2>/dev/null || true
  mv "$APP_DIR" "$RELEASE_BACKUP_DIR/asset-lifecycle-manager.before"
fi

mv "$NEW_DIR" "$APP_DIR"
systemctl enable --now asset-lifecycle
sleep 3

if ! systemctl is-active --quiet asset-lifecycle; then
  systemctl stop asset-lifecycle || true
  rm -rf "$APP_DIR"
  mv "$RELEASE_BACKUP_DIR/asset-lifecycle-manager.before" "$APP_DIR"
  systemctl start asset-lifecycle
  sleep 3
  journalctl -u asset-lifecycle -n 120 --no-pager
  exit 1
fi

curl -fsS -o /tmp/asset-lifecycle-local-index.html http://127.0.0.1:8000/
curl -fsS -o /tmp/asset-lifecycle-public-index.html "$PUBLIC_URL/"

printf 'backup_dir=%s\n' "$RELEASE_BACKUP_DIR"
