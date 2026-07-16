# Single-Server Deployment

This deployment uses Nginx as the only public HTTP entry point. Uvicorn listens on `127.0.0.1:8000` and must not be exposed through the firewall.

## Runtime configuration

Create `/etc/asset-lifecycle/asset-lifecycle.env` with permissions `chmod 600`:

```text
ENV=production
JWT_SECRET_KEY=replace-with-a-new-random-secret
DEFAULT_ADMIN_PASSWORD=replace-with-a-strong-first-admin-password
DATABASE_URL=sqlite:////opt/asset-lifecycle-manager/asset_lifecycle.db
```

Generate `JWT_SECRET_KEY` on the server with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

After the first administrator exists, `DEFAULT_ADMIN_PASSWORD` may be removed from the environment file.

## Database backup and validation

Stop the service before copying the database, or create a consistent SQLite backup:

```bash
sqlite3 /opt/asset-lifecycle-manager/asset_lifecycle.db ".backup '/var/backups/asset-lifecycle/asset_lifecycle-$(date +%F).db'"
sqlite3 /opt/asset-lifecycle-manager/asset_lifecycle.db "PRAGMA integrity_check;"
```

Keep backups outside the application directory and test restoration before each release.

## P0 operational tasks

Install the timers after deploying the application source. The backup directory is
only readable by the application user.

```bash
sudo install -d -o asset-lifecycle -g asset-lifecycle -m 0700 /var/backups/asset-lifecycle
sudo cp deploy/systemd/asset-lifecycle-backup.service deploy/systemd/asset-lifecycle-backup.timer /etc/systemd/system/
sudo cp deploy/systemd/asset-lifecycle-healthcheck.service deploy/systemd/asset-lifecycle-healthcheck.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asset-lifecycle-backup.timer asset-lifecycle-healthcheck.timer
systemctl list-timers 'asset-lifecycle-*'
```

Run each service manually after installation and inspect its local journal output.

```bash
sudo systemctl start asset-lifecycle-backup.service
sudo systemctl start asset-lifecycle-healthcheck.service
sudo systemctl --failed
sudo journalctl -u asset-lifecycle-backup.service -n 50 --no-pager
sudo journalctl -u asset-lifecycle-healthcheck.service -n 50 --no-pager
```

Perform a recovery drill only to a separate temporary path. Do not point the restore
script at the production database path.

```bash
latest=$(sudo find /var/backups/asset-lifecycle -name 'asset_lifecycle-*.db' -type f -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
sudo -u asset-lifecycle /opt/asset-lifecycle-manager/.venv/bin/python -m scripts.restore_database --backup "$latest" --target /var/tmp/asset-lifecycle-restore-drill.db
sqlite3 /var/tmp/asset-lifecycle-restore-drill.db 'PRAGMA integrity_check;'
rm /var/tmp/asset-lifecycle-restore-drill.db
```

## Service setup

Install the systemd unit and start it:

```bash
sudo cp deploy/systemd/asset-lifecycle.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asset-lifecycle
sudo systemctl status asset-lifecycle
```

Check the local health endpoint before configuring Nginx:

```bash
curl http://127.0.0.1:8000/api/health
```

## Nginx and firewall

Install the Nginx template, then validate and reload it:

```bash
sudo cp deploy/nginx/asset-lifecycle.conf /etc/nginx/sites-available/asset-lifecycle
sudo ln -s /etc/nginx/sites-available/asset-lifecycle /etc/nginx/sites-enabled/asset-lifecycle
sudo nginx -t
sudo systemctl reload nginx
```

Allow only SSH and HTTP through the firewall. Do not expose port 8000.

## HTTPS requirement

The supplied Nginx configuration uses HTTP only for temporary public-IP connectivity checks. HTTP exposes login credentials and bearer tokens in transit. Before formal public use, bind a domain, install a TLS certificate, add HTTPS on port 443, and redirect HTTP to HTTPS.
