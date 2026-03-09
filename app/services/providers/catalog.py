from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderDefinition:
    provider_type: str
    label: str
    description: str


PROVIDER_DEFINITIONS = (
    ProviderDefinition(
        provider_type="newapi",
        label="NewAPI（新版）",
        description="使用 /api/user/self 获取余额。",
    ),
    ProviderDefinition(
        provider_type="newapi_legacy",
        label="NewAPI（旧版）",
        description="优先使用 /v1/dashboard/billing/subscription + /v1/dashboard/billing/usage 组合计算余额。",
    ),
    ProviderDefinition(
        provider_type="oneapi",
        label="OneAPI",
        description="使用 OneAPI 兼容的 dashboard billing 接口。",
    ),
)

PROVIDER_DEFINITION_MAP = {
    definition.provider_type: definition for definition in PROVIDER_DEFINITIONS
}


def is_supported_provider_type(provider_type: str) -> bool:
    return provider_type.lower() in PROVIDER_DEFINITION_MAP


def get_provider_options() -> list[dict[str, str]]:
    return [
        {
            "value": definition.provider_type,
            "label": definition.label,
            "description": definition.description,
        }
        for definition in PROVIDER_DEFINITIONS
    ]
