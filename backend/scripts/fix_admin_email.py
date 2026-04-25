#!/usr/bin/env python3
"""Fix admin user email to pass Pydantic validation."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.core.database import async_session_maker
from app.models.user import User


async def fix_admin_email():
    """Fix admin user email."""
    async with async_session_maker() as session:
        # Check if admin exists with bad email
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        admin = result.scalar_one_or_none()

        if not admin:
            print("Admin user not found. Run seed_admin.py first.")
            return

        if admin.email == "admin@localhost":
            await session.execute(
                update(User)
                .where(User.username == "admin")
                .values(email="admin@example.com")
            )
            await session.commit()
            print("Fixed admin email: admin@localhost -> admin@example.com")
        else:
            print(f"Admin email is already valid: {admin.email}")


if __name__ == "__main__":
    asyncio.run(fix_admin_email())
