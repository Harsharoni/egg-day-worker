# Deploying the website on the VPS

The site is a second process next to the worker: uvicorn on localhost:8100,
published through the existing Cloudflare tunnel as `eggday.<site>`.

## 1. systemd unit

```bash
sudo cp deploy/eggday-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eggday-web
journalctl -u eggday-web -f   # logs
```

Adjust `User=`, `WorkingDirectory=` and the `uv` path (`which uv`) if the VPS
layout differs. `.env` is read from the working directory by `config.py`,
so no `EnvironmentFile=` is needed.

## 2. Cloudflare tunnel ingress

Add the hostname **above** the catch-all rule in `~/.cloudflared/config.yml`:

```yaml
ingress:
  - hostname: eggday.<site>
    service: http://localhost:8100
  # ... existing worker.<site> / staff.<site> rules ...
  - service: http_status:404
```

Then route DNS and restart the tunnel:

```bash
cloudflared tunnel route dns <tunnel-name> eggday.<site>
sudo systemctl restart cloudflared
```

## 3. Update deploy

```bash
cd /home/harsh/egg-day-worker && git pull && uv sync && sudo systemctl restart eggday-web
```

The site is read-only: it never calls egg9000 or Google Sheets, and never
writes to Postgres (`initialize()` is worker-only). HTML responses carry
`Cache-Control: public, max-age=30`, so Cloudflare's edge absorbs traffic
spikes.
