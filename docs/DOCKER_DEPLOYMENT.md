# Docker 部署与分发说明

## 1. 本地构建镜像

```bash
docker build -t newapi-credit-logger:0.1.0 .
```

## 2. 本地运行（SQLite）

```bash
docker compose up -d app
```

默认挂载：

- `./logs -> /app/logs`
- `./data -> /app/data`

## 3. 启用 MySQL/PostgreSQL

### MySQL

```bash
docker compose --profile mysql up -d mysql app
```

`DATABASE_URL` 示例：

```text
mysql+pymysql://app:app@mysql:3306/newapi_credit_logger
```

### PostgreSQL

```bash
docker compose --profile postgres up -d postgres app
```

`DATABASE_URL` 示例：

```text
postgresql+psycopg://app:app@postgres:5432/newapi_credit_logger
```

## 4. 镜像分发

版本标签规范：

- 正式版本：`vX.Y.Z`（如 `v0.1.0`）
- 提交版本：`sha-<git_short_sha>`
- 最新稳定：`latest`（仅指向最近一次稳定版）

示例（以 Docker Hub 为例）：

```bash
docker tag newapi-credit-logger:0.1.0 <registry>/<namespace>/newapi-credit-logger:v0.1.0
docker tag newapi-credit-logger:0.1.0 <registry>/<namespace>/newapi-credit-logger:latest
docker push <registry>/<namespace>/newapi-credit-logger:v0.1.0
docker push <registry>/<namespace>/newapi-credit-logger:latest
```

## 5. 回滚

回滚到已发布版本：

```bash
docker pull <registry>/<namespace>/newapi-credit-logger:v0.1.0
docker compose down
docker compose up -d
```

如果使用编排平台，直接将镜像标签回退到目标版本并重新部署。
