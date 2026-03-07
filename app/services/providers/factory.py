from app.services.providers.base import BalanceProvider
from app.services.providers.newapi_provider import NewApiProvider


def get_balance_provider(provider_type: str) -> BalanceProvider:
    if provider_type.lower() == "newapi":
        return NewApiProvider()
    raise ValueError(f"unsupported provider type: {provider_type}")
