"""Unit and integration tests for System 11 Knowledge Base Management & Approval Workflow."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.admin.admin_auth_service import create_access_token

client = TestClient(app)


@pytest.fixture
def admin_headers():
    token = create_access_token(
        admin_id="admin_001",
        username="admin",
        sacco_id="demo_sacco",
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


def test_knowledge_draft_and_approval_workflow(admin_headers):
    # 1. Create a draft policy document
    create_payload = {
        "title": "Guarantor Substitution Guidelines",
        "category": "loans",
        "content": (
            "A member may substitute an existing loan guarantor if the new guarantor meets "
            "the minimum qualifying shares and has no defaulted guarantees. A processing fee "
            "of KES 500 applies for guarantor replacement."
        ),
    }
    res = client.post("/api/admin/knowledge", headers=admin_headers, json=create_payload)
    assert res.status_code == 201
    doc = res.json()
    assert doc["id"].startswith("doc_")
    assert doc["title"] == create_payload["title"]
    assert doc["status"] == "draft"
    assert doc["qdrant_indexed_at"] is None

    doc_id = doc["id"]

    # 2. List documents and find draft
    list_res = client.get("/api/admin/knowledge", headers=admin_headers)
    assert list_res.status_code == 200
    docs = list_res.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Approve and trigger vector sync
    approve_res = client.patch(f"/api/admin/knowledge/{doc_id}/approve", headers=admin_headers)
    assert approve_res.status_code == 200
    approved_doc = approve_res.json()
    assert approved_doc["status"] == "approved"
    assert approved_doc["approved_by"] == "admin_001"
    assert approved_doc["qdrant_indexed_at"] is not None
