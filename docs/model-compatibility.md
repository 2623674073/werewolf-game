# OpenAI-compatible 模型兼容性

项目使用 Chat Completions 风格接口，并要求以下能力：

1. 普通文本回复；
2. `stream=true` 的增量文本；
3. `tools` 与强制工具选择，用于 Pydantic 结构化决策。

“OpenAI-compatible”不是统一认证标准。只有同时通过 `werewolf-game doctor --live-model` 和 `RUN_LIVE_TESTS=1 uv run pytest -m live -s` 的服务，才应标记为已验证。

| Provider / Gateway | Model | Text | Streaming | Structured tools | Status |
| --- | --- | --- | --- | --- | --- |
| 项目维护者的 DeepSeek-compatible 私有网关 | `deepseek-v4-flash` | 已验证 | 已验证 | 本次复验失败：上游连接重置 | Development only；不作为发布门禁 |
| 离线 Demo Runtime | deterministic | CI | CI | CI | Fully verified |

默认 `LLM_TRUST_ENV=false`，模型客户端不会继承系统代理变量；只有明确需要代理时才设置为 `true`。兼容性报告不得包含 Base URL 中的凭据、API Key 或完整私密提示词。

最近一次人工复验日期为 2026-07-17。流式回复通过，结构化工具调用在私有网关返回上游连接失败；这说明文本流式链路可用，但尚不足以将该网关列为完整兼容。应在网关恢复后重新运行两条验证命令，并以连续通过结果更新本表。
