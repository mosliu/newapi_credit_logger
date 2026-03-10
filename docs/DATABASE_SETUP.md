# 数据库初始化（SQLite / MySQL / PostgreSQL）

本项目的“自动建表”基于 Alembic 迁移（推荐方式）。你只需要配置 `DATABASE_URL`，然后执行迁移即可自动创建/升级表结构。

## 1. 推荐方式：Alembic 自动建表（跨库一致）

### MySQL

示例连接串：

```env
DATABASE_URL=mysql+pymysql://app:app@127.0.0.1:3306/newapi_credit_logger?charset=utf8mb4
```

执行迁移（会自动创建表）：

```bash
uv run alembic upgrade head
```

### PostgreSQL

示例连接串：

```env
DATABASE_URL=postgresql+psycopg://app:app@127.0.0.1:5432/newapi_credit_logger
```

执行迁移（会自动创建表）：

```bash
uv run alembic upgrade head
```

## 2. 生成“建表 SQL 语句”（不连接数据库）

如果你希望拿到可直接执行的 `CREATE TABLE ...`/`ALTER TABLE ...` 语句，可以使用 Alembic 的离线 SQL 输出：

### PowerShell（Windows）示例

生成 MySQL 初始化 SQL：

```powershell
$env:DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/newapi_credit_logger'
uv run alembic upgrade head --sql | Out-File -Encoding utf8 "docs/sql/mysql_init.sql"
```

生成 PostgreSQL 初始化 SQL：

```powershell
$env:DATABASE_URL='postgresql+psycopg://user:pass@127.0.0.1:5432/newapi_credit_logger'
uv run alembic upgrade head --sql | Out-File -Encoding utf8 "docs/sql/postgresql_init.sql"
```

## 3. 仓库内已生成的 SQL 文件

当前仓库已提供（由 Alembic 离线生成）：

- `docs/sql/mysql_init.sql`
- `docs/sql/postgresql_init.sql`

提示：

- 这些 SQL 会包含 `alembic_version` 版本表与升级记录语句（这是 Alembic 的标准行为）。
- 当迁移脚本发生变化时，请按第 2 节命令重新生成并覆盖这些 SQL 文件，以保持一致性。

