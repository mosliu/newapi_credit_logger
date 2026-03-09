# Provider API 兼容说明

## 已接入

- `newapi`：新版 NewAPI，使用 `/api/user/self`。
- `newapi_legacy`：旧版 NewAPI，优先使用 `/v1/dashboard/billing/subscription` 与 `/v1/dashboard/billing/usage` 组合计算余额，并兼容无 `/v1` 前缀的同名路径。
- `oneapi`：按 OneAPI 兼容的 dashboard billing 路径处理，优先尝试 `credit_grants`，并兼容 `subscription` 路径。

## 金额单位约定

- 系统统一按“元”落库与展示，保留 2 位小数。
- 旧版 NewAPI 的 `/v1/dashboard/billing/subscription` 返回值按“元”处理。
- 旧版 NewAPI 的 `/v1/dashboard/billing/usage` 返回值按“分”处理，代码会先换算为“元”再参与计算与落库。
- 每次采集同时记录：`额度(limit_amount)`、`使用量(usage_amount)`、`余额(balance)`。

## 调研结论

- NewAPI 官方文档已公开 `/dashboard/billing/subscription`、`/v1/dashboard/billing/subscription`、`/dashboard/billing/usage`、`/v1/dashboard/billing/usage`。
- 用户最新反馈表明旧版 NewAPI 应优先使用 `subscription + usage` 路径，因此代码已调整为以 `/v1/dashboard/billing/subscription` 与 `/v1/dashboard/billing/usage` 为首选。
- OneAPI 官方仓库历史代码中存在 `credit_grants` 与 `subscription` 相关实现，因此当前纳入可选 Provider。

## 暂未接入

- `donehub`：本次已完成仓库与文档入口调研，但未拿到足够稳定的官方接口定义，不在本次代码里直接开放选择，避免误接入。

## 建议

- 新建监控源时，优先按实际站点版本选择 Provider，而不是只填域名。
- 若后续补齐 `donehub` 官方接口定义，可直接按现有 Provider 目录表继续扩展，无需改数据库结构。
