#!/usr/bin/env python3
"""Seed script to create a default admin user."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.user import User
import uuid


async def create_admin():
    """Create default admin user if not exists."""
    async with async_session_maker() as session:
        # Check if admin already exists
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("Admin user already exists")
            return

        # Create admin user
        admin = User(
            id=uuid.uuid4(),
            username="admin",
            email="admin@example.com",
            password_hash=get_password_hash("admin"),
            preferred_auth_method="password",
            is_active=True,
            is_superuser=True,
        )

        session.add(admin)
        await session.commit()

        print("=" * 50)
        print("Default admin user created:")
        print("  Username: admin")
        print("  Password: admin")
        print("=" * 50)
        print("⚠️  Change the password after first login!")


if __name__ == "__main__":
    asyncio.run(create_admin())
