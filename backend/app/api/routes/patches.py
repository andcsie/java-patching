"""Patch analysis routes."""

from fastapi import APIRouter

from app.services.release_notes_service import JDKChange, release_notes_service

router = APIRouter()


@router.get("/changes")
async def get_jdk_changes(
    from_version: str,
    to_version: str,
) -> dict:
    """Get JDK changes between two versions."""
    changes = await release_notes_service.get_changes_between_versions(
        from_version,
        to_version,
    )

    return {
        "from_version": from_version,
        "to_version": to_version,
        "total_changes": len(changes),
        "changes": [
            {
                "version": c.version,
                "change_type": c.change_type,
                "component": c.component,
                "description": c.description,
                "affected_classes": c.affected_classes,
                "affected_methods": c.affected_methods,
                "cve_id": c.cve_id,
                "migration_notes": c.migration_notes,
            }
            for c in changes
        ],
    }


@router.get("/versions")
async def get_supported_versions() -> dict:
    """Get list of supported JDK versions for analysis."""
    # Commonly used JDK LTS versions with patch releases
    versions = {
        "8": ["8.0.352", "8.0.362", "8.0.372", "8.0.382", "8.0.392"],
        "11": [
            "11.0.18",
            "11.0.19",
            "11.0.20",
            "11.0.21",
            "11.0.22",
        ],
        "17": [
            "17.0.6",
            "17.0.7",
            "17.0.8",
            "17.0.9",
            "17.0.10",
        ],
        "21": [
            "21.0.1",
            "21.0.2",
            "21.0.3",
        ],
    }

    return {
        "lts_versions": ["8", "11", "17", "21"],
        "patch_versions": versions,
    }


@router.get("/security-fixes")
async def get_security_fixes(
    from_version: str,
    to_version: str,
) -> dict:
    """Get security fixes between two JDK versions."""
    changes = await release_notes_service.get_changes_between_versions(
        from_version,
        to_version,
    )

    security_fixes = [c for c in changes if c.cve_id is not None]

    return {
        "from_version": from_version,
        "to_version": to_version,
        "total_security_fixes": len(security_fixes),
        "cves": [
            {
                "cve_id": c.cve_id,
                "version": c.version,
                "component": c.component,
                "description": c.description,
                "affected_classes": c.affected_classes,
            }
            for c in security_fixes
        ],
    }
