# Analysis Gateway

本目录提供一个本地 Python 网关，用来承接 Tampermonkey 脚本的异常事件，并把智能分析请求路由到不同提供方。

## 支持的模式

- `local`: 调本地 OpenAI 兼容服务，如 Ollama / LM Studio
- `deepseek`: 调 DeepSeek API

## 快速开始

1. 复制 `config.example.json` 为 `config.json`
2. 填写 `deepseek.api_key`，或把 `local.base_url` 指向本地模型服务
3. 安装依赖：

```bash
pip install -r requirements.txt
```

4. 启动：

```bash
python app.py
```

默认监听 `http://127.0.0.1:8787`。

## 接口

- `GET /health`
- `POST /analyze`

Tampermonkey 脚本会把累计消耗时间序列和当前事件上下文发到这个接口，并通过 `provider_override` 字段实现切换。
