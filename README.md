# NewAPI Credit Logger

一个用于监控多种 API 面板余额/额度的 FastAPI 项目，支持后台管理、定时采集、历史记录查询、失败排查日志，以及 Docker 部署。

## 功能概览

- 支持多监控源配置：`base_url`、`api_key`、`interval_seconds`、`enabled`、`key_owner`、`key_account`、`customer_info`、`key_created_at`、`fee_amount`、`fee_currency`、`remark`
- 支持多 Provider / 多版本接口：
  - `newapi`：新版 NewAPI，走 `/api/user/self`
  - `newapi_legacy`：旧版 NewAPI，优先走 `subscription + usage`
  - `oneapi`：OneAPI 兼容 billing 接口
- 定时采集与手动采集
- 记录每次采集的：
  - `额度(limit_amount)`
  - `使用量(usage_amount)`
  - `余额(balance)`
- 后台管理系统 `/admin`，支持登录保护
- 后台支持“复制新增”监控源（复制除 `api_key` 外的配置）
- 后台监控列表 `/admin/sources`（需登录）
- 普通用户首页 `/ui`（多 Tab：`Key 片段查询`、`API 测试`、`API Key 查询`）
- 兼容保留 `/ui/key-search`（按 key 前缀/后缀片段匹配，结果仅展示脱敏 key）
- 内置 `html_api_test` 同等能力：规则解析、LLM 解析、上游联通测试、Neko Token 查询/导出
- 调试日志、错误日志、上游请求日志分文件输出
- 支持 SQLite / MySQL / PostgreSQL

## 金额规则

- 系统统一按“元”落库与展示
- 所有金额统一保留 2 位小数
- 对旧版 NewAPI：
  - `subscription` 返回按“元”处理
  - `usage` 返回按“分”处理，代码内自动换算为“元”

## 技术栈

- FastAPI
- SQLAlchemy 2.x
- Alembic
- APScheduler
- httpx
- loguru
- Jinja2

## 目录结构

```text
app/
  admin/                 后台页面与路由
  api/                   API 路由与 Schema
  core/                  配置与日志
  db/                    数据库会话与 Base
  models/                ORM 模型
  services/              业务逻辑、Provider、加密等
  tasks/                 定时任务
  ui/                    前台展示页
docs/                    项目文档
migrations/              Alembic 迁移
tests/                   自动化测试
main.py                  启动入口
```

## 环境要求

- Python 3.11+
- 推荐使用 `uv`

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

复制示例配置：

```bash
copy .env.example .env
```

重点配置项：

```env
APP_VERSION=0.1.2
DATABASE_URL=sqlite:///./data/newapi_credit_logger.db
LOG_LEVEL=DEBUG
DEFAULT_POLL_INTERVAL_SECONDS=300
SCHEDULER_REQUEST_DELAY_SECONDS=1
SCHEDULER_MISFIRE_GRACE_SECONDS=30
SCHEDULER_MAX_WORKERS=20
API_KEY_ENCRYPT_SECRET=change-me-in-production
ADMIN_PASSWORD=change-me-admin-password
ADMIN_SESSION_SECRET=change-me-admin-session-secret
```

生产环境请务必修改：

- `API_KEY_ENCRYPT_SECRET`
- `ADMIN_PASSWORD`
- `ADMIN_SESSION_SECRET`

### 3. 初始化数据库

```bash
uv run alembic upgrade head
```

### 4. 启动服务

```bash
uv run python "main.py"
```

默认地址：

- API：`http://127.0.0.1:8000/api`
- 普通用户首页：`http://127.0.0.1:8000/ui`
- 兼容入口（Key 查询）：`http://127.0.0.1:8000/ui/key-search`
- 后台：`http://127.0.0.1:8000/admin`
- 后台监控列表：`http://127.0.0.1:8000/admin/sources`

## 后台登录

- 后台使用单一管理员密码保护
- 首次访问 `/admin` 会跳转到 `/admin/login`
- 登录状态通过 Session Cookie 维持

默认密码取自 `.env` 中的：

```env
ADMIN_PASSWORD=...
```

## Provider 说明

### `newapi`

- 请求路径：`/api/user/self`

### `newapi_legacy`

- 优先请求：
  - `/v1/dashboard/billing/subscription`
  - `/v1/dashboard/billing/usage`
- 回退请求：
  - `/dashboard/billing/subscription`
  - `/dashboard/billing/usage`
- 余额计算：`额度 - 使用量`

### `oneapi`

- 兼容 `credit_grants` / `subscription` 路径

更多细节见：`docs/PROVIDER_API_COMPATIBILITY.md`

## 日志说明

日志目录默认是 `logs/`，包含：

- `app.log`：应用通用日志
- `error.log`：错误日志
- `scheduler.log`：调度与采集结果日志
- `upstream.log`：上游接口请求调试日志

当前默认日志级别：`DEBUG`

上游请求日志会记录：

- 请求 URL
- HTTP 状态码
- `content-type`
- 响应片段 `response_excerpt`
- 非 JSON 响应错误

## 数据库说明

当前 `api_key_source` 额外支持业务元数据字段：

- `key_account`
- `customer_info`
- `key_created_at`
- `fee_amount`
- `fee_currency`

当前 `balance_record` 记录字段包括：

- `limit_amount`
- `usage_amount`
- `balance`
- `currency`
- `http_status`
- `latency_ms`
- `error_message`
- `response_excerpt`

如果你调整了金额字段或采集结构，建议直接重建 SQLite 数据库：

```bash
del .\data\newapi_credit_logger.db
uv run alembic upgrade head
```

## Docker

见：`docs/DOCKER_DEPLOYMENT.md`

## 常用命令

### 启动开发环境

```bash
uv run python "main.py"
```

### 执行迁移

```bash
uv run alembic upgrade head
```

### 运行测试

```bash
uv run pytest
```

### 编译级静态校验

```bash
python -m compileall "app"
```

## 已知说明

- 某些站点返回的并不是 JSON，而是 HTML 错误页、登录页或反代页；此时可查看 `logs/upstream.log`
- 旧版 NewAPI 与兼容系统接口差异较大，新增站点时请正确选择 `provider_type`
- 若当前终端环境对 `multiprocessing` 或 `loguru enqueue` 有权限限制，可能影响某些命令行导入验证，但不影响正常服务启动环境

## 文档

- 开发计划：`docs/DEVELOPMENT_PLAN.md`
- 数据库初始化：`docs/DATABASE_SETUP.md`
- 发布日志：`docs/RELEASE_NOTES.md`
- Provider 兼容说明：`docs/PROVIDER_API_COMPATIBILITY.md`
- Docker 部署：`docs/DOCKER_DEPLOYMENT.md`
- GUI 规格：`docs/GUI_SPECIFICATION.md`
