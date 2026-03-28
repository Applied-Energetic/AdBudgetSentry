# AdBudgetSentry beta1.4 更新说明

上一个版本：`beta1.3`  
当前版本：`beta1.4`

## 本次更新内容

### 1. 后台新增实例详情页

新增页面：

- `GET /admin/instances/{instance_id}`

详情页包含：

- 实例基础信息
- 最近心跳与最近采集
- 最近采样趋势图
- 最近采样历史表
- 最近分析记录
- 最近告警记录
- 最近错误记录

### 2. 后台新增实例详情 JSON 接口

新增接口：

- `GET /admin/api/instances/{instance_id}`
- `GET /admin/api/instances/{instance_id}/history`

用途：

- 供后续前端重构时复用
- 供独立调试和排障

### 3. 总览页支持跳转实例详情

后台首页的实例列表现在可以点击进入详情页，方便从总览直接下钻排查。

### 4. 文档补充

新增文档：

- `docs/接口说明.md`
- `docs/项目开发说明.md`
- `docs/Gemini3Pro-前端改造提示词.md`

## 关键文件变更

- `code/analysis_gateway/admin_ui.py`
- `code/analysis_gateway/app.py`
- `code/analysis_gateway/database.py`
- `code/analysis_gateway/models.py`
- `code/analysis_gateway/README.md`

## 推荐提交信息

### Commit Title

```text
feat: add instance detail page, history API and beta1.4 docs
```

### Commit Body

```text
- add admin instance detail page
- add instance detail/history JSON APIs
- add capture trend chart and history table
- link dashboard rows to instance detail
- add beta1.4 release notes and docs
```

## 推荐推送说明

```text
beta1.4 已完成，新增后台实例详情页、最近采样历史接口和简单趋势图，后台总览可直接下钻到实例详情，方便定位采样异常、告警触发和发送链路问题。
```

