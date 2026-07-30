"""Pure portfolio-math domain layer: allocation, concentration, and P&L.

No module in this package performs I/O, network calls, or DB access --
every function here is a plain, typed transformation over `Holding` values
(see `types.py`). This is deliberate: CLAUDE.md calls out this layer as
needing to "approach full coverage" since a bug here means wrong numbers
shown to a user, and pure functions over synthetic fixtures are what makes
that coverage cheap to write and trustworthy to read.
"""
