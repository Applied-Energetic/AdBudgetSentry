# Windows 服务器与 Cloudflare Tunnel 部署

这份文档用于把当前这台 Windows 台式机长期运行成 AdBudgetSentry 服务器，目标是：

- 后端静默常驻
- Cloudflare Tunnel 常驻
- 日志可查
- 外部用户可稳定访问后台页面

补充：

- 常用运维命令见 [运维命令速查.md](/E:/Code/AdBudgetSentry/docs/运维命令速查.md)

## 1. 当前方案

本仓库默认采用：

- `Windows 计划任务` 启动后端
- `Windows 计划任务` 启动 `cloudflared`
- `logs/` 保存日志
- `run/` 保存 PID
- `secrets/` 保存本地 token 文件

这样做的原因很简单：

- 比手动开两个命令行稳定
- 比直接双击脚本更适合长期运行
- 比把所有东西塞进 Windows 服务更容易看日志和维护

## 2. 你要准备什么

### 2.1 本机准备

- Windows 10/11
- Python 已安装
- 项目路径固定在 `E:\Code\AdBudgetSentry`
- 已能本地访问 `http://127.0.0.1:8787/admin`

### 2.2 Cloudflare 侧准备

你需要：

- 一个放在 Cloudflare 的域名
- Cloudflare Zero Trust / Tunnels 可用
- 已创建 Tunnel
- 已配置公网 hostname 指向本机后端

官方文档：

- [Cloudflare Tunnel 下载](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)
- [Cloudflare Tunnel 基础设置](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Windows 运行 cloudflared 官方说明](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/local-management/as-a-service/windows/)

## 3. 推荐的 Cloudflare Tunnel 配置方式

当前推荐你用“远程托管 Tunnel + 本地 token 文件”的方式。

优点：

- 配置简单
- Tunnel 路由规则在 Cloudflare 面板维护
- 本地只需要保存 token
- 更适合你这种单机个人项目

### 3.1 在 Cloudflare 面板里做什么

1. 登录 Cloudflare Zero Trust
2. 创建一个 Tunnel
3. 添加一个 Public Hostname
4. 目标地址填写：

```text
http://127.0.0.1:8787
```

例如：

- `admin.your-domain.com` -> `http://127.0.0.1:8787`

5. 保存后，Cloudflare 会给你一个 Tunnel Token

### 3.2 本机保存 token

在本机创建目录：

```powershell
New-Item -ItemType Directory -Force E:\Code\AdBudgetSentry\secrets
```

把 token 写入：

```powershell
Set-Content -Path E:\Code\AdBudgetSentry\secrets\cloudflared-token.txt -Value "你的 Tunnel Token"
```

说明：

- 这个文件已在 `.gitignore` 中忽略
- 不要提交到 GitHub

## 4. 安装 cloudflared

### 4.1 下载

从官方下载安装 `cloudflared.exe`。建议固定到这个路径：

```text
C:\Cloudflared\cloudflared.exe
```

如果你实际路径不同，后面的安装命令里把路径改掉即可。

### 4.2 手动试跑

先手动验证一次：

```powershell
E:\Code\AdBudgetSentry\scripts\start-cloudflared-background.ps1 -CloudflaredExe "C:\Cloudflared\cloudflared.exe"
```

然后看日志：

```powershell
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component cloudflared -Tail 80
```

如果日志里能看到 tunnel connected，说明链路通了。

## 5. 让后端静默运行

### 5.1 第一次本地验证

先本地后台跑起来：

```powershell
E:\Code\AdBudgetSentry\scripts\start-analysis-gateway-background.ps1 -EnsureDeps
```

看日志：

```powershell
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component gateway-stdout -Tail 80
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component gateway-stderr -Tail 80
```

然后访问：

- `http://127.0.0.1:8787/admin`
- `http://127.0.0.1:8787/admin/alerts`

## 6. 安装 Windows 计划任务

注意：下面这一步建议用“管理员 PowerShell”执行。

### 6.1 安装后端启动任务

```powershell
E:\Code\AdBudgetSentry\scripts\install-analysis-gateway-task.ps1 -EnsureDeps
```

这个任务会：

- 开机启动
- 静默运行
- 以 `SYSTEM` 账户运行
- 自动调用后台启动脚本

### 6.2 安装 cloudflared 启动任务

```powershell
E:\Code\AdBudgetSentry\scripts\install-cloudflared-task.ps1 -CloudflaredExe "C:\Cloudflared\cloudflared.exe"
```

### 6.3 立即启动任务

```powershell
schtasks /Run /TN "AdBudgetSentry-AnalysisGateway"
schtasks /Run /TN "AdBudgetSentry-Cloudflared"
```

## 7. 日志保存与查询

### 7.1 日志文件位置

后端：

- `logs/analysis-gateway.stdout.log`
- `logs/analysis-gateway.stderr.log`

Tunnel：

- `logs/cloudflared.log`
- `logs/cloudflared.stdout.log`
- `logs/cloudflared.stderr.log`

### 7.2 查询最新日志

查看后端输出：

```powershell
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component gateway-stdout -Tail 100
```

查看后端错误：

```powershell
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component gateway-stderr -Tail 100
```

查看 tunnel：

```powershell
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component cloudflared -Tail 100
```

按关键字过滤：

```powershell
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component gateway-stderr -Pattern "Traceback"
E:\Code\AdBudgetSentry\scripts\get-server-logs.ps1 -Component cloudflared -Pattern "error"
```

## 8. 你现在要配合做什么

按这个顺序做就行：

1. 确认 `code\analysis_gateway\config.json` 已配置模型和 PushPlus
2. 下载 `cloudflared.exe` 到 `C:\Cloudflared\cloudflared.exe`
3. 在 Cloudflare 面板创建 Tunnel，并把 hostname 指向 `http://127.0.0.1:8787`
4. 把 Tunnel Token 写到 `E:\Code\AdBudgetSentry\secrets\cloudflared-token.txt`
5. 先手动执行：

```powershell
E:\Code\AdBudgetSentry\scripts\start-analysis-gateway-background.ps1 -EnsureDeps
E:\Code\AdBudgetSentry\scripts\start-cloudflared-background.ps1 -CloudflaredExe "C:\Cloudflared\cloudflared.exe"
```

6. 本地和公网都访问一次后台页面
7. 确认日志正常
8. 最后再安装两个计划任务

## 9. 验证清单

你应该检查这些点：

- 本地 `http://127.0.0.1:8787/admin` 可访问
- 公网域名可访问后台页面
- `GET /readyz` 正常
- `cloudflared.log` 没有持续报错
- 重启电脑后页面仍可访问
- 油猴脚本还能正常上报心跳、采集和告警

## 10. 运维建议

- 不要暴露数据库文件，只暴露 Web/API
- Tunnel 对外域名建议只给后台，不给其他无关端口
- 定期备份 `data/app.db`
- 定期清理过大的日志文件
- 后面如果外部用户增多，再考虑把 SQLite 升级到 PostgreSQL
