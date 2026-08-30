# Secrets and environment management

This project keeps runtime secrets out of git and expects each environment to source credentials from a local secret file or a system-level environment source.

## Required principles

- Never commit real `.env` files, API keys, DB credentials, or TLS material to the repository.
- Keep the app-level secret file private and restrict permissions to the owner account.
- Use a strong `SECRET_KEY` in production and rotate it immediately after any suspected leak.
- Prefer environment injection for CI and production; do not store secrets in application source files.

## Local development

Use the repo-local template as the starting point:

```bash
cp .env.example backend/.env
```

or, if you want a service-specific environment file:

```bash
cp backend/.env.example backend/.env
```

The backend loader intentionally reads `backend/.env` for database configuration, making the service-specific file the canonical local runtime path. Note that running backend code from the repository root may also load a repo-root `.env` file via `load_dotenv()`, so avoid putting conflicting settings in the repo-root `.env`.

For Raspberry Pi or systemd deployments, keep the runtime file under a protected path such as:

```bash
/etc/fantasy-football-pi/backend.env
```

with permissions:

```bash
sudo chown root:fantasy-football-pi /etc/fantasy-football-pi/backend.env
sudo chmod 600 /etc/fantasy-football-pi/backend.env
```

## Production storage convention

The recommended production pattern is:

- store values in `/etc/fantasy-football-pi/backend.env`
- ensure the service user has read access
- leave the file readable only by the owner and group required by the service
- avoid copying the file into the repository or a container layer

This matches the project’s systemd deployment patterns and keeps secrets separated from code artifacts.

## Required variables

At minimum, production requires a valid `SECRET_KEY` and `DATABASE_URL`.

Key runtime variables include:

- `APP_ENV`
- `SECRET_KEY`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `FRONTEND_ALLOWED_ORIGINS`
- `AUTH_COOKIE_SECURE`
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` for the advisor feature
- `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`, and Yahoo OAuth tokens

The canonical examples are located in:

- `.env.example`
- `backend/.env.example`

## CI and GitHub Actions

GitHub Actions should inject secrets through repository or environment secrets instead of hard-coding values into workflow YAML. Common examples include:

- `DATABASE_URL`
- `SECRET_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`
- any cloud or hosting credentials used by release automation

The repository includes a secrets scanning workflow (`.github/workflows/secrets-scan.yml`) that runs gitleaks on pull requests and pushes.

## Rotation policy

Rotate a secret immediately if:

- it was committed to git or a log file
- it was exposed in a ticket, screenshot, or support chat
- a developer workstation or a CI runner is no longer trusted
- a credential is suspected to be used outside the intended environment

Example rotation flow:

```bash
# generate a new secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# update it in the production env file
sudo nano /etc/fantasy-football-pi/backend.env

# reload the service
sudo systemctl restart fantasy-football-backend
```

After rotation, verify the app restarts successfully and that the `/health` endpoint returns healthy state before resuming normal traffic.

## Secret scanning and validation

Run the built-in validation script:

```bash
python3 backend/scripts/validate_secrets.py
```

This script checks for common production misconfigurations such as missing `SECRET_KEY`, weak values, and overly permissive `.env` permissions.

## Notes

- Keep root and service-level `.env` files outside the repository.
- Prefer using `.env.example` as a documented template and not a source of truth for real secrets.
- If a credential must be shared, use a time-limited, scoped secret and rotate it on a schedule.
