"""SQLAlchemy 2.0 async engine, session factory, and declarative models.

This is the *only* package in the codebase allowed to know a connection
string or SQL dialect. Everything above it -- services, routers, the cache
module -- goes through `db/session.py`'s session factory and the
repository classes built on top of it, so swapping SQLite for Postgres
later is a `DATABASE_URL` + driver change, not a rewrite.
"""
