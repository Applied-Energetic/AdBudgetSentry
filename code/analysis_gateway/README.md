# Analysis Gateway

本目录现在承担两类职责：

1. 接收 Tampermonkey 采集端上报的 `ingest / heartbeat / error`
2. 继续提供已有的 `/analyze` 智能分析能力

更完整的项目说明见：

- `../../docs/接口说明.md`
- `../../docs/项目开发说明.md`

## 当前能力

- `SQLite` 本地持久化
- 实例心跳记录
- 采集事件记录
- 采集错误记录
- 告警发送回执记录
- 实例健康状态聚合
- 本地后台健康页
- 大模型分析接口

## 快速开始

1. 复制 `config.example.json` 为 `config.json`
2. 填写 `deepseek.api_key`，或者把 `local.base_url` 指向本地模型服务
3. 安装依赖：

```bash
pip install -r requirements.txt
```

4. 启动：

```bash
python app.py
```

默认监听：

```text
http://127.0.0.1:8787
```

默认数据库路径：

```text
<repo>/data/app.db
```

也可以用环境变量覆盖：

```powershell
$env:ADBUDGET_DB_PATH="E:\Code\AdBudgetSentry\data\app.db"
```

## 接口

### 系统状态

- `GET /health`
- `GET /healthz`
- `GET /readyz`

### 采集接入

- `POST /ingest`
- `POST /heartbeat`
- `POST /error`
- `POST /alert-record`

### 后台查看

- `GET /`
- `GET /admin/summary`
- `GET /admin/instances`
- `GET /admin/alerts`
- `GET /admin/api/alerts`
- `GET /admin/instances/{instance_id}`
- `GET /admin/api/instances/{instance_id}`
- `GET /admin/api/instances/{instance_id}/history`

说明：

- `GET /admin/alerts` 是后台告警中心页面，支持按账号关键字、发送状态、告警类型和日期范围筛选。
- `GET /admin/api/alerts` 是告警历史 JSON 接口，适合后续前端异步查询或二次开发。

### 智能分析

- `POST /analyze`

## 建议的接入顺序

1. 先用油猴脚本接 `POST /heartbeat`
2. 再接 `POST /ingest`
3. 在后台页确认实例状态是否变化
4. 最后再把告警和 AI 总结完全迁移到后端
