# AdBudgetSentry

面向快手磁力金牛投流场景的轻量化监控与智能分析工具仓库。

## 目录

- `code/userscripts/`: Tampermonkey 用户脚本
- `code/analysis_gateway/`: Python 智能分析网关，支持本地模型与 DeepSeek API 切换
- `references/pages/`: 参考网页快照与静态资源
- `docs/`: 需求、方案、开发文档

## 当前建议工作流

1. 在浏览器中安装 `code/userscripts/` 下的用户脚本。
2. 如需智能分析，在本机启动 `code/analysis_gateway/`。
3. 在脚本面板中选择分析模式：
   - `local`: 调本地 OpenAI 兼容模型服务
   - `deepseek`: 由本地网关转发到 DeepSeek API
4. 参考 `docs/需求梳理与技术方案.md` 与 `docs/4060环境Qwen2.5可行性分析.md` 调整路线。
