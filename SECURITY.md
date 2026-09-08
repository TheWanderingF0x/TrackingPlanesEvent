# Security policy

## Reporting a vulnerability

If you find a credential leak, insecure default, or other security issue in this repository, please **do not open a public issue** with the secret included.

Email or message the maintainer privately, rotate the exposed OpenSky OAuth client immediately on the [OpenSky account page](https://opensky-network.org/), then share details of the leak path (file/commit).

## Secrets in this project

This project is designed to be **open source**. Real credentials must never live in git.

| Safe to commit | Never commit |
|----------------|--------------|
| `.env.example` (placeholders only) | `.env` with real `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET` / `GOOGLE_MAPS_API_KEY` |
| `config/airlines_europe.yaml` | API tokens, private keys, `settings.conf` with passwords |
| Code under `src/`, `scripts/`, `deploy/` | `data/raw`, `data/curated`, collector logs |

Setup for contributors:

```bash
cp .env.example .env
# edit .env locally — it is gitignored
```

Before every push, run:

```bash
python scripts/check_no_secrets.py
```

If the check fails, fix or unstage the flagged files. If a secret was already pushed, **revoke/rotate** the OpenSky API client and treat the old secret as public.
