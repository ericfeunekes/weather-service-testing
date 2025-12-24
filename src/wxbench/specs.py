"""Utility functions for fetching and parsing provider API specifications."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping
import json

import httpx

DEFAULT_SPEC_DIR = Path(__file__).resolve().parents[2] / "specs"

# Public, unauthenticated documentation endpoints.
PROVIDER_SPEC_URLS: Mapping[str, str] = {
    "msc-geomet": "https://api.weather.gc.ca/openapi",
}


def _open_client(client: httpx.Client | None) -> httpx.Client:
    if client is not None:
        return client
    return httpx.Client(follow_redirects=True, timeout=httpx.Timeout(10.0))


def fetch_specs(
    *,
    provider_urls: Mapping[str, str] | None = None,
    output_dir: Path | None = None,
    client: httpx.Client | None = None,
) -> list[Path]:
    """Download provider specs to disk.

    The function keeps side effects contained to the filesystem and HTTP
    boundary; callers may inject an :class:`httpx.Client` for testing.
    """

    targets = provider_urls or PROVIDER_SPEC_URLS
    destination = output_dir or DEFAULT_SPEC_DIR
    destination.mkdir(parents=True, exist_ok=True)

    session = _open_client(client)
    created: list[Path] = []
    try:
        for provider, url in targets.items():
            response = session.get(url)
            response.raise_for_status()
            spec = response.json()
            path = destination / f"{provider}.json"
            path.write_text(json.dumps(spec, indent=2, sort_keys=True))
            created.append(path)
    finally:
        if client is None:
            session.close()
    return created


def load_spec(path: Path) -> Mapping[str, Any]:
    """Load a saved OpenAPI/JSON document from disk."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_paths(spec: Mapping[str, Any]) -> Iterable[str]:
    """Yield all documented HTTP path templates from a spec."""

    paths = spec.get("paths", {})
    if not isinstance(paths, Mapping):
        return []
    return paths.keys()


if __name__ == "__main__":
    saved = fetch_specs()
    for path in saved:
        print(f"wrote {path}")
