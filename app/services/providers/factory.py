from app.services.providers.base import BalanceProvider
from app.services.providers.compatible_billing_provider import CompatibleBillingProvider
from app.services.providers.newapi_provider import NewApiProvider


def get_balance_provider(provider_type: str) -> BalanceProvider:
    normalized = provider_type.lower()

    if normalized == "newapi":
        return NewApiProvider()
    if normalized == "newapi_legacy":
        return CompatibleBillingProvider(
            credit_grants_paths=(),
            subscription_paths=(
                "/v1/dashboard/billing/subscription",
                "/dashboard/billing/subscription",
            ),
            usage_paths=(
                "/v1/dashboard/billing/usage",
                "/dashboard/billing/usage",
            ),
        )
    if normalized == "oneapi":
        return CompatibleBillingProvider(
            credit_grants_paths=(
                "/dashboard/billing/credit_grants",
                "/v1/dashboard/billing/credit_grants",
            ),
            subscription_paths=(
                "/v1/dashboard/billing/subscription",
                "/dashboard/billing/subscription",
            ),
        )
    raise ValueError(f"unsupported provider type: {provider_type}")
