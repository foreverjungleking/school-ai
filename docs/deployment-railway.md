# Railway public demo deployment

This deploys the repository as managed PostgreSQL, a FastAPI backend, and a
React/Vite frontend. The database stays private. The browser calls the backend's
public HTTPS origin; the backend reaches PostgreSQL over private networking.

Railway deprecated Config as Code for new services in 2026. Existing services
that already use `railway.json` or `railway.toml` may continue doing so only
until Railway's documented December 1, 2026 cutoff. The checked-in JSON files
are retained as executable configuration for an already-enrolled service and as
a reviewable record of the intended values; **configure the same values in the
dashboard for the first deployment**. Do not introduce Railway Infrastructure
as Code before the manual deployment succeeds. See Railway's current
[Config as Code notice](https://docs.railway.com/config-as-code),
[monorepo guide](https://docs.railway.com/deployments/monorepo), and
[variable reference](https://docs.railway.com/variables/reference).

If Config as Code is already active, file values override dashboard values. Its
config-file path does not follow a service's Root Directory: set the absolute
path `/railway.json` for Backend and `/frontend/railway.json` for Frontend.
New services that cannot enable these files should leave the config-file field
unset and use the dashboard settings below.

## Services

Create a Railway project connected to `foreverjungleking/school-ai`. Add
PostgreSQL and two services from the repository. Examples below name them
`Postgres`, `Backend`, and `Frontend`; adjust references if the names differ.
The finished project should contain exactly those three services.

### PostgreSQL

Use managed PostgreSQL without enabling its public TCP proxy. The backend can
consume its private `DATABASE_URL` through a reference variable. Railway lists
the managed service's [PostgreSQL variables](https://docs.railway.com/databases/postgresql)
and explains [private networking](https://docs.railway.com/networking/private-networking).

### Backend

- Source: GitHub repository `foreverjungleking/school-ai`, branch `main`
- Root directory: `/`
- Config file, only for an existing Config as Code service: `/railway.json`
- Build: `python -m pip install .`
- Pre-deploy:
  `python -c "from alembic.config import main; main(argv=['upgrade', 'head'])"`
- Start: `uvicorn school_ai.api.app:app --host 0.0.0.0 --port $PORT`
- Health path: `/health`

Set:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
APP_ENV=production
ALLOWED_CORS_ORIGINS=https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}
MAX_SOLVE_SECONDS=15
```

`DATABASE_URL` remains backend-only. The application normalizes Railway-style
`postgres://` or `postgresql://` URLs to SQLAlchemy's installed psycopg driver.
The application service caps solver runs even if a client requests longer.

Generate a temporary public domain for the backend. The API must be public
because frontend JavaScript executes in the visitor's browser. Uvicorn binds to
Railway's injected `PORT` without reload/debug mode. Railway's
[health-check documentation](https://docs.railway.com/deployments/healthchecks)
describes deployment readiness; `/health` intentionally does not query the DB.

### Schema and synthetic data

The pre-deploy command runs
`python -c "from alembic.config import main; main(argv=['upgrade', 'head'])"`.
Calling Alembic's supported Python entry point avoids relying on either a
console-script directory in Railway's `PATH` or a nonexistent `alembic.__main__`
module. Alembic is a normal production dependency in `pyproject.toml`, so
`python -m pip install .` installs it. The command upgrades in place, never
calls `drop_all()`, and is repeatable. After its first success, use a one-off
Railway SSH command in the deployed backend container to seed explicitly. Link
the Railway CLI to the project/environment, or copy the Backend service's exact
SSH command from the dashboard, then run:

```bash
railway ssh --service Backend -- python -m school_ai.demo_seed
```

Seeding is not startup behavior. Repeating it preserves a complete seed and
adds nothing; a partial school dataset is rejected rather than deleted. There
is no public reset endpoint.

### Frontend

- Source: GitHub repository `foreverjungleking/school-ai`, branch `main`
- Root directory: `/frontend`
- Config file, only for an existing Config as Code service:
  `/frontend/railway.json`
- Build: `npm ci && npm run build`
- Start: `npm run start`
- Health path: `/`

After generating the backend domain, set this build-time public value:

```text
VITE_API_BASE_URL=https://${{Backend.RAILWAY_PUBLIC_DOMAIN}}
```

Never put secrets in `VITE_*`; these values are compiled into browser assets.
`serve --single` serves `dist/` with SPA history fallback, not Vite's dev server.
See Railway's [Vite guide](https://docs.railway.com/guides/vite) and
[frontend-variable guide](https://docs.railway.com/guides/frontend-environment-variables).

Generate a temporary frontend domain, rebuild after setting the API URL, and
verify connectivity. Configure watch paths in the dashboard (`/frontend/**` for
Frontend and the paths recorded in root `railway.json` for Backend) when Config
as Code is not active.

## CORS and custom domains

Production never defaults to `*`; without `ALLOWED_CORS_ORIGINS`, no
cross-origin browser callers are allowed. Supply exact origins (scheme, host,
optional port, no path), comma-separated. During domain transition, use:

```text
ALLOWED_CORS_ORIGINS=https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}},https://app.<custom-domain>
```

Attach `app.<custom-domain>` to the frontend. Railway displays the CNAME and
ownership TXT records for the DNS provider and handles HTTPS. Do not commit DNS
credentials. The backend may keep its Railway domain or use
`api.<custom-domain>`; when it changes, update `VITE_API_BASE_URL` and rebuild.
Follow Railway's current [custom-domain flow](https://docs.railway.com/networking/domains/working-with-domains).

## Deployment sequence

1. Confirm the canvas contains exactly `Postgres`, `Backend`, and `Frontend`.
2. Keep Postgres private; do not enable its TCP proxy.
3. Connect Backend to the GitHub repository's `main` branch. Enter its root,
   build, pre-deploy, start, health, and variables exactly as listed above.
4. Deploy Backend. Confirm logs show Alembic reaching `head`; a failed
   pre-deploy prevents the new deployment from starting.
5. Explicitly seed once with Railway SSH.
6. Under Backend Networking, generate a temporary Railway public domain.
7. Verify `GET /health`, `/docs`, `/teachers`, `/rooms`, `/student-groups`, and
   `/activities` on that HTTPS origin.
8. Connect Frontend to the same repository and `main`, set root `/frontend`, and
   enter its build/start/health settings.
9. Set `VITE_API_BASE_URL=https://<backend-railway-domain>` and deploy Frontend.
10. Generate its Railway public domain. Set Backend
    `ALLOWED_CORS_ORIGINS=https://<frontend-railway-domain>` and redeploy Backend
    if Railway does not trigger it automatically.
11. Rebuild Frontend whenever `VITE_API_BASE_URL` changes; it is build-time
    browser configuration.
12. Perform the live smoke test. Only after it passes, attach the purchased
    frontend domain and add Railway's displayed DNS records.
13. Wait for HTTPS, update final CORS/API origins, and redeploy as required.

## Production smoke test

1. Open the frontend HTTPS URL and confirm its API-connected state.
2. Confirm Teachers, Rooms, Student Groups, and Activities load synthetic data.
3. Create a logical schedule through the UI.
4. Generate a draft and confirm CP-SAT returns `FEASIBLE` or `OPTIMAL`.
5. Verify assigned lessons render in the weekly timetable.
6. Explicitly publish the draft and verify its `PUBLISHED` state.
7. Generate another draft, compare the two versions, and verify unchanged,
   moved/changed, added, and removed sections are presented as returned by API.
8. Redeploy or restart Backend, reload the same schedule, and confirm versions
   and lessons persisted in PostgreSQL.
9. Request an absent item such as `GET /teachers/999999`; expect 404.
10. Submit malformed or invalid draft input in `/docs`; expect 422 validation or
    the documented structured solver failure, never a fabricated timetable.
11. Confirm unexpected failures return the generic API error without Python
    stack traces or secrets in the response.
12. In browser developer tools, confirm the configured frontend origin receives
    valid CORS headers. Send an `Origin` header for an arbitrary origin and
    confirm no permissive `Access-Control-Allow-Origin` response is returned.

Railway/DNS configuration and this live smoke test are manual; repository tests
require no Railway credentials.
