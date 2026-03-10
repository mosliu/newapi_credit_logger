# 发布日志（Release Notes）

本项目采用 `MAJOR.MINOR.PATCH` 语义化版本号。

## v0.1.2 - 2026-03-10

### Changed

- 默认采集周期从 60 秒调整为 5 分钟（`DEFAULT_POLL_INTERVAL_SECONDS=300`）。
- 普通用户 Key 片段查询安全阈值调整：前缀/后缀匹配最少 12 位。
- 普通用户页面顶栏入口收敛为 3 个：`Key 查询`、`API 测试`、`API Key 查询`；监控列表页需后台登录后访问。
- `API Key 查询` 增加 NewAPI 新版/老版选择，并按版本走不同接口查询逻辑。
- 移除普通用户首页重复的分段标签栏，改为通过顶栏按钮切换功能。

### Verification

- 自动化测试：`uv run pytest` 通过。

## v0.1.1 - 2026-03-10

### Added

- 新增普通用户首页 `/ui`，统一承载多 Tab 功能入口。
- 新增首页一级标签：`Key 片段查询`、`API 测试`、`Neko 查询`。
- 新增 API 工具接口：
  - `GET /api/config`
  - `POST /api/parse/rule`
  - `POST /api/parse/llm`
  - `POST /api/test`
  - `POST /api/neko/query`
- 新增页面版本号显示：
  - 普通用户页面顶栏显示版本号。
  - 管理后台顶栏显示版本号。

### Changed

- `tab` 参数兼容策略更新：
  - 新值：`key-search`、`api-test`、`neko-query`
  - 兼容旧值：`api-tools`（自动映射到 `api-test`）
- 应用版本来源统一为配置项 `APP_VERSION`，并同步用于 FastAPI `app.version`。

### Docs

- 新增发布日志文档 `docs/RELEASE_NOTES.md`。
- 更新 `README.md`，补充 `APP_VERSION` 配置说明与发布日志文档入口。
- 新增数据库初始化文档 `docs/DATABASE_SETUP.md`，并提供 `docs/sql/mysql_init.sql`、`docs/sql/postgresql_init.sql`（由 Alembic 离线 `--sql` 生成）。

### Verification

- 自动化测试：`uv run pytest tests` 通过。

## v0.1.0 - 2026-03-07

### Added

- 项目初始版本发布：
  - 监控源管理（含后台登录保护）
  - 定时采集与手动采集
  - 多 Provider 兼容
  - 监控查询页与详情页
  - Docker 交付文件
