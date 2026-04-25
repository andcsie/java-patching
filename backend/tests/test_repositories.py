"""Tests for repository endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_repository(client: AsyncClient, auth_headers):
    """Test creating a repository."""
    response = await client.post(
        "/api/repositories",
        headers=auth_headers,
        json={
            "name": "test-repo",
            "url": "https://github.com/example/test.git",
            "description": "Test repository",
            "branch": "main",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-repo"
    assert data["url"] == "https://github.com/example/test.git"
    assert data["branch"] == "main"


@pytest.mark.asyncio
async def test_list_repositories(client: AsyncClient, auth_headers):
    """Test listing repositories."""
    # Create a repo first
    await client.post(
        "/api/repositories",
        headers=auth_headers,
        json={
            "name": "list-test-repo",
            "url": "https://github.com/example/list.git",
        },
    )

    response = await client.get("/api/repositories", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_repository(client: AsyncClient, auth_headers):
    """Test getting a specific repository."""
    # Create a repo first
    create_response = await client.post(
        "/api/repositories",
        headers=auth_headers,
        json={
            "name": "get-test-repo",
            "url": "https://github.com/example/get.git",
        },
    )
    repo_id = create_response.json()["id"]

    response = await client.get(f"/api/repositories/{repo_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "get-test-repo"


@pytest.mark.asyncio
async def test_update_repository(client: AsyncClient, auth_headers):
    """Test updating a repository."""
    # Create a repo first
    create_response = await client.post(
        "/api/repositories",
        headers=auth_headers,
        json={
            "name": "update-test-repo",
            "url": "https://github.com/example/update.git",
        },
    )
    repo_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/repositories/{repo_id}",
        headers=auth_headers,
        json={"description": "Updated description"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_delete_repository(client: AsyncClient, auth_headers):
    """Test deleting a repository."""
    # Create a repo first
    create_response = await client.post(
        "/api/repositories",
        headers=auth_headers,
        json={
            "name": "delete-test-repo",
            "url": "https://github.com/example/delete.git",
        },
    )
    repo_id = create_response.json()["id"]

    response = await client.delete(f"/api/repositories/{repo_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's deleted (soft delete)
    get_response = await client.get(f"/api/repositories/{repo_id}", headers=auth_headers)
    # Should still exist but be inactive
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_create_repository_unauthorized(client: AsyncClient):
    """Test creating a repository without auth fails."""
    response = await client.post(
        "/api/repositories",
        json={
            "name": "unauth-repo",
            "url": "https://github.com/example/unauth.git",
        },
    )
    assert response.status_code == 403
