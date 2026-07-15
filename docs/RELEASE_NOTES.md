# 发布日志（Release Notes）

本项目采用 `MAJOR.MINOR.PATCH` 语义化版本号。

## v0.1.4 - 2026-07-14

### Added

- 新增 `app/core/timezone.py` 统一时区工具：`fmt_cst`（UTC → 东八区格式化，注册为 Jinja 过滤器 `|cst`）、`cst_to_utc_naive`（东八区输入 → UTC 查询）。
- 后台新增监控源表单 Provider 行新增 `Anyrouter` 快捷按钮，点击后自动选择 `NewAPI（旧版）` 并填充地址。
- 后台新增监控源页面 `Key创建时间` 进入时默认初始化为当前时间减 3 分钟（编辑页有值时不覆盖）。

### Changed

- 全站展示时间统一为东八区（UTC+8）：监控源分析、监控源列表（后台/前台）、采集记录、同步记录、监控详情、图表 X 轴、首页 API 查询时间列（固定 `Asia/Shanghai`）。
- 时间筛选输入统一按东八区解释后转 UTC 查询：采集记录页日期筛选（含“今天”）、监控详情页 `start_at/end_at` 参数。
- 默认采集周期从 300 秒调整为 1200 秒（`DEFAULT_POLL_INTERVAL_SECONDS=1200`）。
- `Key创建时间` 输入框限定年份范围（`min/max`），年份显示收敛为 4 位。

### Fixed

- 修复调度器 `reload_jobs` 将已有任务以 `next_run_time=None` 重建导致任务被暂停的问题（APScheduler 3.x 中 `None` 表示暂停）：任意新增/编辑/删除监控源后，仅最后操作的源继续采集，其余全部静默停摆。现改为重建时保留原计划时间。

### Verification

- 自动化测试：`pytest` 通过（23 passed）。
- 监控源分析页端到端验证：窗口内首末余额与变化量计算、失败/窗口外记录排除、东八区时间展示均正确。

## v0.1.3 - 2026-06-10

### Added

- `api_key_source` 新增最新采集快照字段，保存最新采集状态、额度、用量、余额、币种、采集时间、HTTP 状态、耗时与错误信息。
- `API Key 查询` 页面新增 `Anyrouter` 快捷按钮，点击后自动填充 `https://anyrouter.top` 并切换为 NewAPI 老版。

### Changed

- 管理后台监控源列表与普通用户 Key 片段查询改为直接读取 `api_key_source` 快照，避免记录量大时反复扫描 `balance_record`。
- 额度刷新时会继续写入 `balance_record` 历史记录，同时同步更新监控源最新快照。

### Migration

- 新增 Alembic 迁移 `a4c9b2d7e8f1`，会补齐快照字段、创建 `balance_record(source_id, checked_at, id)` 复合索引，并从历史记录回填每个监控源最新状态。

### Verification

- 自动化测试：`uv run pytest` 通过（21 passed）。
- 迁移验证：SQLite 空库执行 `uv run alembic upgrade head` 通过。

## v0.1.2 - 2026-03-10

### Changed

- 默认采集周期从 60 秒调整为 5 分钟（`DEFAULT_POLL_INTERVAL_SECONDS=300`）。
- 普通用户 Key 片段查询安全阈值调整：前缀/后缀匹配最少 12 位。
- 普通用户页面顶栏入口收敛为 3 个：`Key 查询`、`API 测试`、`API Key 查询`；监控列表页需后台登录后访问。
- `API Key 查询` 增加 NewAPI 新版/老版选择，并按版本走不同接口查询逻辑。
- 移除普通用户首页重复的分段标签栏，改为通过顶栏按钮切换功能。

### Fixed

- 修复 `API Key 查询` 接口 `/api/neko/query` 报 500（Settings 缺少 `log_preview_len`）的问题，并补齐 `LOG_PREVIEW_LEN` 配置项（控制上游调试日志预览截断长度）。
- 优化 `API Key 查询` 上游返回非 JSON（如 WAF/JS Challenge HTML）时的报错提示与日志信息（增加 `content-type`），便于快速定位站点防护拦截问题。
- 修正 `API Key 查询` 中 “NewAPI 老版” 的实现：余额信息改为使用 `/v1/dashboard/billing/subscription` + `/v1/dashboard/billing/usage`（并兼容 `/dashboard/...`），避免错误走到 `/api/user/self`。
- 关闭 `API Key 查询` 中 `NewAPI 老版` 的调用日志查询：旧版无调用日志接口，前端不再发起 `/api/log/token` 请求。

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
