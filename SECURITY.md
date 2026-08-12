# Security and Privacy Policy

## Reporting a vulnerability

Open a GitHub issue with the `security` label, or contact the maintainer
privately. Do not include credentials, tokens or personal data in the report.

## Secrets

- No credential is ever hardcoded. Every secret is read from an environment
  variable in `src/lms/config.py` (`Settings.from_env`).
- `.env` is git-ignored. Only `.env.example`, which contains empty
  placeholders, is committed.
- `Settings.google_places_api_key` is declared with `repr=False`, so an
  accidental `print(settings)` or log line cannot leak the key.
- If a key is ever committed, rotate it first, then rewrite history.

## Data sources and licensing

- The only data source is the public OpenStreetMap Overpass API. OSM data is
  published under the Open Database License (ODbL 1.0) and requires
  attribution, which the generated brief includes.
- Scraping Google Maps HTML is intentionally **not** implemented: it violates
  the Google Maps/Google Earth Terms of Service. Use the official Places API
  with your own key if you need that data.
- Requests are read-only `POST`s that carry a descriptive `User-Agent`.
  Public Overpass instances are shared infrastructure: keep the retry and
  backoff defaults, and do not run tight scan loops.

## Personal data

- The collected fields (business name, category, address, public phone,
  public website, opening hours) are business contact details already
  published in OSM, not private personal data.
- Some records may nevertheless identify a sole practitioner. If you use this
  data for outreach in the EU or in Türkiye (KVKK), you are the data
  controller: honour opt-out requests, state your identity in the first
  contact, and delete records on request.
- Generated CSV, SQLite and Markdown files under `data/` are git-ignored. Do
  not commit collected datasets to a public repository.

## Network behaviour

- Outbound traffic is limited to the configured Overpass endpoints.
- TLS verification is always on. `REQUESTS_CA_BUNDLE` exists for corporate
  proxies with TLS inspection; verification is never disabled in code.
- Run `python -m lms.cli doctor` to see exactly which endpoints are contacted.
