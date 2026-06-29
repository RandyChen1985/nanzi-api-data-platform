"""Shared Jinja2 environments for SQL template rendering."""
from jinja2 import BaseLoader, DebugUndefined, Environment, Undefined


class SqlLabUndefined(Undefined):
    """Treat undefined Jinja variables as SQL NULL in lab preview."""

    def __str__(self) -> str:
        return "NULL"

    def __html__(self) -> str:
        return "NULL"

    def __iter__(self):
        return iter([])

    def __bool__(self) -> bool:
        return False


# Standard template env: keep {{ var }} when undefined for later replacement
TEMPLATE_ENV = Environment(loader=BaseLoader(), undefined=DebugUndefined)

# SQL Lab env: undefined variables become NULL for column fetching
SQL_LAB_ENV = Environment(loader=BaseLoader(), undefined=SqlLabUndefined)
