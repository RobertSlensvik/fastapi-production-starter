"""Re-export models so Alembic autogenerate picks them up.

When adding new models, import them here.
"""

from app.db.models.user import User

__all__ = ["User"]
