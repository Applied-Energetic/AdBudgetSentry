# Windows 启动说明

本文档适用于在 Windows 上启动 `AdBudgetSentry`。

## 1. 前置条件

启动前请确认：

1. 已安装 Python 3，并且 `python` 命令可用
2. 项目路径为 `E:\Code\AdBudgetSentry`
3. 如需公网隧道，已安装 `cloudflared.exe`

后端服务默认监听：

```text
http://127.0.0.1:8787
```

默认数据库路径：

```text
E:\Code\AdBudgetSentry\data\app.db
```

## 2. 最简单的启动方式

在资源管理器里直接双击：

```text
E:\Code\AdBudgetSentry\scripts\start-analysis-gateway.cmd
```

这会调用：

```text
E:\Code\AdBudgetSentry\scripts\start-analysis-gateway.ps1
```

它会自动做这些事：

1. 在 `code\analysis_gateway\.venv` 创建虚拟环境
2. 安装 `requirements.txt`
3. 如果 `config.json` 不存在，则从 `config.example.json` 复制一份
4. 启动后端服务

启动成功后，浏览器打开：

```text
http://127.0.0.1:8787/admin
```

## 3. PowerShell 前台启动

如果你想在 PowerShell 里直接看运行输出，执行：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\start-analysis-gateway.ps1
```

如果想指定端口：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\start-analysis-gateway.ps1 -Port 8787
```

说明：

- 这种方式是前台运行
- 关闭窗口或按 `Ctrl + C` 后服务停止

## 4. PowerShell 后台启动

如果你想让服务在后台运行，执行：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\start-analysis-gateway-background.ps1 -EnsureDeps
```

说明：

- 首次启动建议加 `-EnsureDeps`
- 后台 PID 文件会写到：

```text
E:\Code\AdBudgetSentry\run\analysis-gateway.pid
```

- 日志会写到：

```text
E:\Code\AdBudgetSentry\logs\analysis-gateway.stdout.log
E:\Code\AdBudgetSentry\logs\analysis-gateway.stderr.log
```

如果需要强制重启后台服务：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\start-analysis-gateway-background.ps1 -ForceRestart -EnsureDeps
```

## 5. 查看日志

如果服务已在后台运行，可查看：

```text
E:\Code\AdBudgetSentry\logs\
```

也可以运行现有日志脚本：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\get-server-logs.ps1
```

## 6. 停止后台服务

后台模式下，可先读取 PID 文件：

```text
E:\Code\AdBudgetSentry\run\analysis-gateway.pid
```

然后执行：

```powershell
Stop-Process -Id (Get-Content E:\Code\AdBudgetSentry\run\analysis-gateway.pid)
```

## 7. 可选：启动 cloudflared 隧道

如果你需要把本地服务通过 Cloudflare Tunnel 暴露出去，先准备：

1. `C:\Cloudflared\cloudflared.exe`
2. `E:\Code\AdBudgetSentry\secrets\cloudflared-token.txt`

前台运行：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\run-cloudflared.ps1
```

后台运行：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\start-cloudflared-background.ps1
```

cloudflared 日志目录：

```text
E:\Code\AdBudgetSentry\logs\
```

## 8. 首次启动后你需要做的事

首次启动后请检查：

1. `E:\Code\AdBudgetSentry\code\analysis_gateway\config.json` 是否已生成
2. 其中的 AI provider、API key、PushPlus 配置是否已填好
3. 浏览器访问 `http://127.0.0.1:8787/admin` 是否正常打开后台
4. Tampermonkey 脚本里的后端地址是否指向 `http://127.0.0.1:8787`

## 9. 推荐启动顺序

推荐顺序：

1. 启动 Analysis Gateway
2. 打开 `http://127.0.0.1:8787/admin`
3. 安装并启用 Tampermonkey 脚本
4. 打开磁力金牛页面，观察脚本面板是否开始上报
5. 如需公网访问，再启动 cloudflared

## 10. 我给你的最短建议

如果你只是想先跑起来，直接用这条：

```powershell
cd E:\Code\AdBudgetSentry
powershell -ExecutionPolicy Bypass -File .\scripts\start-analysis-gateway.ps1
```

然后打开：

```text
http://127.0.0.1:8787/admin
```
