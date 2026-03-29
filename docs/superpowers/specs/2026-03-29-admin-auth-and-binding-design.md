# 后台登录与油猴绑定方案

## 目标

为后台监控系统增加用户体系，让每个用户只能看到自己的实例和监控数据；同时为油猴脚本设计一套安全、低摩擦的绑定流程，使实例可以归属到登录用户。

## 当前现状

- 后端目前以 `instance_id` 为核心，没有用户、会话、设备或实例归属表。
- 后台接口默认是全局可见的管理视图，还没有用户隔离。
- 采集链路已经稳定，油猴脚本会上报 `instance_id`、账户信息、页面信息和采样数据。
- 现有 `SignedPayload` 有 `timestamp / nonce / signature` 字段，但尚未形成完整鉴权机制。

## 设计原则

1. 不重写现有采集链路，优先在现有 FastAPI 和数据库上增量扩展。
2. 后台 Web 登录采用邮箱验证码，无密码体系，减少用户记忆成本。
3. 会话长期有效，支持多设备同时登录，不强制频繁重新登录。
4. 实例归属通过显式认领完成，不从账户名或页面字段推断用户归属。
5. 油猴脚本不直接保存邮箱或用户 ID，只使用短期绑定令牌完成归属。

## 数据库设计

### 新增表

#### `users`

- `id`
- `email`
- `email_normalized`
- `status`
- `created_at`
- `last_login_at`

说明：
- `email_normalized` 唯一，用于统一小写和空格处理。
- `status` 建议包含 `active / disabled`。

#### `email_otps`

- `id`
- `user_id` 可为空
- `email_normalized`
- `code_hash`
- `purpose`
- `expires_at`
- `consumed_at`
- `attempt_count`
- `created_at`

说明：
- 验证码只存哈希，不存明文。
- 每条验证码单次有效，过期和使用后失效。

#### `user_sessions`

- `id`
- `user_id`
- `session_token_hash`
- `device_id` 可为空
- `user_agent`
- `ip`
- `created_at`
- `last_seen_at`
- `expires_at`
- `revoked_at`

说明：
- 支持一个用户多个会话并存。
- 服务端仅保存 token 哈希。

#### `user_devices`

- `id`
- `user_id`
- `device_label`
- `device_fingerprint`
- `first_seen_at`
- `last_seen_at`

说明：
- 设备信息用于后续展示和会话管理，不参与强校验。

#### `instance_owners`

- `instance_id`
- `user_id`
- `claimed_at`
- `claim_source`
- `last_verified_at`

说明：
- 用独立归属表，不把身份字段塞进现有实例遥测表。
- `instance_id` 作为主键，表示一个实例当前归属于一个用户。

## 后端接口设计

### 认证接口

#### `POST /auth/email/request-otp`

入参：
- `email`

行为：
- 标准化邮箱
- 生成 6 位验证码
- 存储哈希和过期时间
- 发送邮件

#### `POST /auth/email/verify-otp`

入参：
- `email`
- `otp`
- `device_name` 可选

返回：
- 登录成功后的用户信息
- 长期会话 Cookie

行为：
- 校验 OTP
- 自动创建用户
- 创建 `user_sessions`
- 更新 `last_login_at`

#### `POST /auth/logout`

行为：
- 撤销当前会话

#### `POST /auth/logout-all`

行为：
- 撤销当前用户所有会话

#### `GET /me`

返回：
- 当前登录用户基本信息

#### `GET /me/sessions`

返回：
- 当前用户所有设备会话

#### `DELETE /me/sessions/{session_id}`

行为：
- 删除某一个设备会话

## 监控数据接口改造

新增一组用户视角接口，替代当前全局管理页直接读取全量数据的方式：

- `GET /me/dashboard`
- `GET /me/instances`
- `GET /me/instances/{instance_id}`
- `GET /me/alerts`
- `GET /me/alerts/export.csv`
- `POST /me/instances/{instance_id}/meta`
- `DELETE /me/instances/{instance_id}`

行为：
- 所有查询都先通过 `instance_owners` 过滤，只返回当前用户拥有的实例。
- 没有归属关系的实例不可读、不可改、不可删。

## 会话方案

### Web 后台

- 使用随机高熵 opaque token。
- 浏览器通过 HTTP-only Cookie 保存会话。
- 会话默认长期有效，例如 90 天。
- 每次访问刷新 `last_seen_at`，可做滑动续期。

### 多设备登录

- 一个用户允许多个 `user_sessions` 并存。
- 不限制手机、电脑、平板同时在线。
- 后台提供“设备管理”页面，允许用户手动登出某台设备。

## 油猴脚本绑定方案

### 目标

让用户在登录后台后，把当前浏览器中的油猴实例安全认领到自己的账户下。

### 推荐流程

1. 用户先登录后台。
2. 后台实例页或“绑定实例”页生成一个短期 `claim_token`，例如 5 分钟有效。
3. 用户在油猴脚本中点击“绑定到我的后台”，粘贴或自动带入 `claim_token`。
4. 油猴脚本在下一次心跳或通过专门接口提交：
   - `instance_id`
   - `claim_token`
5. 服务端校验 `claim_token` 后，将 `instance_id -> user_id` 写入 `instance_owners`。
6. 后台刷新后，该实例出现在当前用户的监控列表中。

### 推荐接口

#### `POST /me/instance-claims/token`

返回：
- `claim_token`
- `expires_at`

#### `POST /ingest/claim-instance`

入参：
- `instance_id`
- `claim_token`

行为：
- 校验令牌是否属于某个登录用户
- 完成实例归属写入

## 为什么不用邮箱直传绑定

不推荐让油猴脚本直接上传邮箱或用户 ID，因为：

- 邮箱可以伪造
- 用户 ID 可以枚举
- 浏览器脚本本身不适合持有敏感身份信息

短期绑定令牌更简单，也更安全。

## 前端改造顺序

### 第一阶段

- 增加登录页
- 增加邮箱验证码流程
- 新增用户态 `me` 接口
- 新后台前端切到用户接口

### 第二阶段

- 增加实例认领页面
- 油猴脚本增加绑定入口
- 实例详情页显示归属状态

### 第三阶段

- 增加设备管理
- 增加退出所有设备
- 增加邮箱发送频控与风控

## 风险与约束

1. 现有 `instance_id` 有一部分是由页面信息派生的，如果页面信息变化可能导致新实例出现，因此归属关系必须基于显式认领。
2. 登录功能上线后，旧 `/admin` 全局接口不应继续对外开放，至少要收缩到管理员专用或开发环境专用。
3. 邮件发送需要新的基础设施，例如 SMTP 或邮件服务商。
4. 如果后续需要更强安全性，可以启用现有签名字段，逐步校验脚本上报真实性。

## 建议结论

最稳的路径是：

- 继续保留现有采集与分析后端
- 新增用户、会话、实例归属三套最小表
- 后台前端改走 `me/*` 用户接口
- 油猴脚本通过一次性 `claim_token` 完成实例绑定

这样可以在不推翻现有系统的前提下，把“单人总后台”平滑升级成“多用户、自有实例隔离”的正式产品形态。
