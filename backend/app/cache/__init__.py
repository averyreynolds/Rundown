"""The one caching module in the codebase (CLAUDE.md's explicit instruction).

A single generic `cache_entries` table (see `app/db/models.py`) behind
`CacheRepository`, with per-data-type TTLs centralized in `ttl_policy.py`.
Every provider service (U4-U7) reads and writes through this same
repository -- no service maintains its own bespoke cache table or ad-hoc
in-memory dict.
"""
