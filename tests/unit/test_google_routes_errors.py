import httpx
import respx
import pytest

from wxbench.providers.errors import ProviderTransientError
from wxbench.providers.google_routes import fetch_google_route


def test_google_routes_transient_error() -> None:
    with respx.mock:
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").respond(500)
        with httpx.Client() as client:
            with pytest.raises(ProviderTransientError):
                fetch_google_route(
                    origin="A",
                    destination="B",
                    api_key="demo",
                    client=client,
                )
