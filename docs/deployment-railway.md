# Railway public demo deployment

This deploys the repository as managed PostgreSQL, a FastAPI backend, and a
React/Vite frontend. The database stays private. The browser calls the backend's
public HTTPS origin; the backend reaches PostgreSQL over private networking.

The checked-in `railway.json` files use Railpack. Railway supports service root
directories and watch paths for monorepos, cross-service reference variables,
pre-deploy commands, and HTTP health checks. See its
[configuration reference](https://docs.railway.com/config-as-code/reference),
[monorepo guide](https://docs.railway.com/deployments/monorepo), and
[variable reference](https://docs.railway.com/variables/reference).

## Services

Create a Railway project connected to `foreverjungleking/school-ai`. Add
PostgreSQL and two services from the repository. Examples below name them
`Postgres`, `Backend`, and `Frontend`; adjust references if the names differ.

### PostgreSQL

Use managed PostgreSQL without enabling its public TCP proxy. The backend can
consume its private `DATABASE_URL` through a reference variable. Railway lists
the managed service's [PostgreSQL variables](https://docs.railway.com/databases/postgresql)
and explains [private networking](https://docs.railway.com/networking/private-networking).

### Backend

- Root directory: `/`
- Config file: `/railway.json`
- Build: `python -m pip install .`
- Pre-deploy: `alembic upgrade head`
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

The pre-deploy command runs `alembic upgrade head`. It upgrades in place, never
calls `drop_all()`, and is repeatable. After its first success, use a one-off
Railway shell in the backend service to seed synthetic data explicitly:

```bash
python -m school_ai.demo_seed
```

Seeding is not startup behavior. Repeating it preserves a complete seed and
adds nothing; a partial school dataset is rejected rather than deleted. There
is no public reset endpoint.

### Frontend

- Root directory: `/frontend`
- Config file: `/frontend/railway.json`
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
verify connectivity. The config files declare watch paths so each service tracks
only its part of the monorepo.

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

1. Create the project, connect GitHub, and add private PostgreSQL.
2. Configure the backend root/config and the DB reference/backend variables.
3. Deploy it; pre-deploy applies migrations.
4. Explicitly seed once in a backend service shell.
5. Generate the backend domain and verify `/health`.
6. Configure the frontend root/config and `VITE_API_BASE_URL`.
7. Build it, generate its temporary domain, and add that origin to CORS.
8. Attach the purchased frontend domain and add Railway's displayed DNS records.
9. Wait for HTTPS, update final CORS/API origins, and redeploy where needed.
10. Perform the smoke test.

## Production smoke test

- Backend `/health` returns 200 with the production environment.
- Teachers, rooms, and activities return seeded synthetic data.
- Frontend loads over HTTPS and reports a connected API.
- Creating a schedule and generating a CP-SAT draft succeeds.
- The timetable displays valid assignments; solver failures display none.
- Version comparison reports changes and explicit publish updates the current
  publication.
- After backend restart/redeploy, versions and lessons remain present.
- Browser responses contain no stack traces/secrets, the DB is not public, and
  an unlisted CORS origin is rejected.

Railway/DNS configuration and this live smoke test are manual; repository tests
require no Railway credentials.
