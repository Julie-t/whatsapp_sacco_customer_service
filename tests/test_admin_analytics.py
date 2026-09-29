"""Unit and integration tests for System 11 Admin Analytics & Reporting."""

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


def test_get_overview_kpis(admin_headers):
    res = client.get("/api/admin/analytics/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_members" in data
    assert "total_questions_answered" in data
    assert "knowledge_gaps_count" in data
    assert "open_escalations_count" in data
    assert "groundedness_score_pct" in data
    assert data["groundedness_score_pct"] == 100.0


def test_get_top_questions(admin_headers):
    res = client.get("/api/admin/analytics/questions", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "topic_or_query" in item
        assert "count" in item
        assert "percentage" in item


def test_get_goal_insights(admin_headers):
    res = client.get("/api/admin/analytics/goals", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_get_language_breakdown(admin_headers):
    res = client.get("/api/admin/analytics/languages", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "english_pct" in data
    assert "swahili_pct" in data
    assert "mixed_sheng_pct" in data


def test_get_evaluations_history(admin_headers):
    res = client.get("/api/admin/analytics/evaluations", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        item = data[-1]
        assert "recall_5" in item
        assert "groundedness" in item
        assert "hallucinations" in item


def test_get_system_health(admin_headers):
    res = client.get("/api/admin/analytics/health", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["database"] == "healthy"
    assert "overall" in data


def test_export_report_csv(admin_headers):
    res = client.get("/api/admin/reports/export", headers=admin_headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    content = res.text
    assert "Metric,Value" in content
    assert "Total Members," in content
