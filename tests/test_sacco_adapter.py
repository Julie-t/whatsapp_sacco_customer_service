"""Unit tests for SACCO API Adapter Interface & Data Minimization (System 12.4, 12.5, 12.11, 12.13)."""

from unittest.mock import MagicMock, patch
import pytest

from app.services.members.sacco_adapter import (
    DatabaseSaccoAdapter,
    HttpSaccoAdapter,
    SaccoApiUnavailableError,
    SaccoTenantMismatchError,
    SaccoTimeoutError,
    SavingsBalance,
    LoanRecord,
)


def test_http_adapter_timeout_handling():
    adapter = HttpSaccoAdapter(base_url="http://fake-sacco.api", timeout_seconds=0.1)

    with patch("httpx.Client.get") as mock_get:
        import httpx
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")

        with pytest.raises(SaccoTimeoutError):
            adapter.get_savings_balance("mem_001", "demo_sacco")


def test_http_adapter_unavailable_handling():
    adapter = HttpSaccoAdapter(base_url="http://fake-sacco.api")

    with patch("httpx.Client.get") as mock_get:
        import httpx
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(SaccoApiUnavailableError):
            adapter.get_member("mem_001", "demo_sacco")


def test_http_adapter_tenant_isolation_forbidden():
    adapter = HttpSaccoAdapter(base_url="http://fake-sacco.api")

    with patch("httpx.Client.get") as mock_get:
        response = MagicMock()
        response.status_code = 403
        mock_get.return_value = response

        with pytest.raises(SaccoTenantMismatchError):
            adapter.get_member("mem_001", "unauthorized_sacco")


def test_http_adapter_parses_balance():
    adapter = HttpSaccoAdapter(base_url="http://fake-sacco.api")

    with patch("httpx.Client.get") as mock_get:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "account_number": "SAV-9901",
            "account_type": "savings",
            "balance": 45000.0,
            "currency": "KSh",
            "available_balance": 45000.0,
        }
        mock_get.return_value = response

        bal = adapter.get_savings_balance("mem_001", "demo_sacco")
        assert bal is not None
        assert bal.balance == 45000.0
        assert bal.account_number == "SAV-9901"


def test_http_adapter_change_request_read_write_separation():
    adapter = HttpSaccoAdapter(base_url="http://fake-sacco.api")

    with patch("httpx.Client.post") as mock_post:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "id": "req_12345",
            "member_id": "mem_001",
            "sacco_id": "demo_sacco",
            "change_type": "phone_number",
            "status": "pending",
            "requested_at": "2026-09-10T12:00:00Z",
        }
        mock_post.return_value = response

        res = adapter.submit_change_request(
            member_id="mem_001",
            sacco_id="demo_sacco",
            change_type="phone_number",
            payload={"new_phone": "+254711223344"},
        )
        assert res.status == "pending"
        assert res.request_id == "req_12345"
