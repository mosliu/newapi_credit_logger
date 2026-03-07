# 项目级执行规范

本文件用于约束本仓库的开发执行流程。

## 1. 计划驱动开发（强制）

- 开发必须以 [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) 为唯一执行计划。
- 实施顺序按阶段 A -> B -> C -> D -> E 推进。
- 未经用户确认，不得跳过阶段或扩大需求范围。

## 2. 计划实时更新（强制）

- 每完成一个任务项，必须立即同步更新 `docs/DEVELOPMENT_PLAN.md`：
  - 对应任务打勾 `[x]`
  - 更新“当前进度看板”
  - 在“进度日志”追加时间与完成内容
- 若发生范围、架构、优先级变化，必须更新“计划变更记录”。

## 3. 文档目录规范（强制）

- 除根目录 `README.md` 外，所有文档统一放在 `docs/` 目录。
- 新增文档默认放到 `docs/`，按主题命名，避免重复文档。

## 4. 当前冻结需求（开发基线）

- 数据库：SQLite、MySQL、PostgreSQL。
- 监控源配置字段至少包含：`base_url`、`api_key`、`interval_seconds`、`enabled`、`key_owner`、`remark`。
- 系统能力：定时采集余额、入库、查询展示、详细日志、Docker 部署与镜像分发交付。
