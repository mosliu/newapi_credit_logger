# 发布日志（Release Notes）

本项目采用 `MAJOR.MINOR.PATCH` 语义化版本号。

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
