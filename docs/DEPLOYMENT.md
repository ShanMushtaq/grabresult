# GrabResult Deployment Guide

Three routes, cheapest first. **Local use needs no deployment at all** —
`python run.py` on your own computer is the recommended way to run GrabResult.

## Route 1 — Your own computer (recommended, free forever)

Just run it locally (see `docs/SETUP.md`). Your data stays with you,
nothing sleeps, nothing expires.

## Route 2 — Render.com free tier (public URL, ~10 minutes)

Render gives free web hosting. Limits: the free service **sleeps after
15 minutes idle** (first visit wakes it in ~30s) and its disk is
**ephemeral** — the database resets on redeploy.

Steps (you do these once in your browser):

1. Create a free account at https://render.com and connect your GitHub.
2. Push this folder to a GitHub repository (or use Render's "deploy from zip").
3. In Render: **New → Web Service →** select the repo.
   Render auto-detects `render.yaml`: build `pip install -r requirements.txt`,
   start `gunicorn run:app ...`.
4. Click **Deploy**. When it turns green, open the URL Render gives you.
5. Test: visit `/api/health` — you should see `{"ok": true, ...}`.

**Keeping your data:** download your XLSX exports regularly, or back up
`instance/grabresult.db`. For a database that survives restarts, attach a
Render persistent disk (paid) or use Route 3.

## Route 3 — Any VPS / Docker host (full control)

```bash
# On the server:
docker build -t grabresult .
docker run -d -p 5000:5000 \
  -v grabresult-data:/data \
  -e GRABRESULT_SECRET_KEY="$(openssl rand -hex 32)" \
  --name grabresult grabresult
```

The `/data` volume keeps your database, uploads and exports across restarts.
Works on Hetzner, DigitalOcean, Oracle Cloud free tier, or a home server.

## Production checklist

- [ ] Set `GRABRESULT_SECRET_KEY` to a random value (`.env.example` shows how).
- [ ] Serve behind HTTPS (Render does this automatically; for VPS use
      Caddy/Nginx as a reverse proxy).
- [ ] Back up `instance/grabresult.db` regularly.
- [ ] Keep `GRABRESULT_RPS=1.0` (or lower) to stay polite to free sources.
- [ ] Never put the `instance/` folder in a public git repo.

## What was NOT done

The app was **not** deployed to a public URL during development: publishing
requires an account signup + repo push that only you can do. Everything
needed is prepared (`Procfile`, `render.yaml`, `Dockerfile`,
`requirements.txt`) and the app was verified running in production mode
below.

## Production-mode verification (done 2026-10-29)

```
$ gunicorn run:app --bind 127.0.0.1:5057 --workers 2 --threads 4 --timeout 120
$ curl http://127.0.0.1:5057/api/health   → {"ok": true, ...}
$ curl http://127.0.0.1:5057/             → 200, full UI served
```

Gunicorn serves the app cleanly with multiple workers; the same command is
what `Procfile`/`render.yaml`/`Dockerfile` use.
