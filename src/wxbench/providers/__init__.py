"""Provider adapters sit at the boundary.

Each provider module should expose a small interface for fetching data, keeping
HTTP configuration, retries, and auth details isolated from the pure domain
layer. Use dependency injection for clients and clocks to keep integration
points testable.
"""

__all__ = []
