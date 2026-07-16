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
