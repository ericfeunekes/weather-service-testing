# Provider specs

This folder stores provider documentation snapshots used in tests and contract docs.

## Refreshing the MSC GeoMet OpenAPI snapshot

Run the helper script (no authentication required) to download the current public OpenAPI document:

```bash
PYTHONPATH=src python scripts/fetch_specs.py
```

The script writes `specs/msc-geomet.json` with the latest published content from `https://api.weather.gc.ca/openapi`.
