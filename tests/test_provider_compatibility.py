from fastapi.testclient import TestClient

from app.main import app
from app.services.providers.compatible_billing_provider import CompatibleBillingProvider


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict,
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)
        self.headers = headers or {"content-type": "application/json"}

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, responses: dict[str, _FakeResponse]):
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, headers: dict[str, str] | None = None):
        return self._responses[url]


def test_compatible_provider_reads_credit_grants(monkeypatch) -> None:
    provider = CompatibleBillingProvider(
        credit_grants_paths=("/dashboard/billing/credit_grants",),
        subscription_paths=("/v1/dashboard/billing/subscription",),
    )

    responses = {
        "https://example.com/dashboard/billing/credit_grants": _FakeResponse(
            200,
            {"total_available": "12.34", "currency": "USD"},
        )
    }

    monkeypatch.setattr(
        "app.services.providers.compatible_billing_provider.httpx.Client",
        lambda timeout: _FakeClient(responses),
    )

    result = provider.fetch_balance("https://example.com", "sk-test", 2)

    assert result.success is True
    assert str(result.balance) == "12.34"
    assert result.currency == "USD"


def test_admin_form_shows_multiple_provider_choices() -> None:
    client = TestClient(app)

    login = client.post(
        "/admin/login",
        data={"password": "change-me-admin-password"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    response = client.get("/admin/sources/new")

    assert response.status_code == 200
    assert 'value="newapi"' in response.text
    assert 'value="newapi_legacy"' in response.text
    assert 'value="oneapi"' in response.text
