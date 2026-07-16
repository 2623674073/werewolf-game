# 发言内容审核 MCP 实现流程

本文说明狼人杀业务如何启动独立的 MCP 服务，并在游戏运行过程中通过 MCP Client 审核公开发言。首版只实现一个 `review_speech` Tool，使用 stdio 传输，不依赖 Codex、浏览器或远程 MCP 平台。

## 1. 目标与边界

完整调用链如下：

```text
Agent 生成发言
    │
    ▼
GameEngine 判断事件是否为公开 speech
    │
    ▼
SpeechModerator 应用端口
    │
    ▼
McpSpeechModerator（AgentScope MCPClient）
    │  stdio / JSON-RPC
    ▼
Werewolf Speech Moderation MCP Server
    │
    ▼
OpenAI-compatible 模型结构化审核
    │
    ▼
allowed / blocked / unavailable
    │
    ▼
持久化公开 speech 与内部 speech_moderated 事件
```

首版明确不包含：

- Streamable HTTP、OAuth 和远程部署。
- MCP Resources、Prompts、Sampling 或 Tasks。
- React 直接连接 MCP。
- 私密狼人讨论、预言家结果和其他私密行动审核。

领域模型不依赖 MCP。游戏引擎只依赖应用层 `SpeechModerator` 协议，AgentScope 和 MCP SDK 都位于基础设施层。

## 2. MCP Tool 契约

MCP Server 只暴露一个工具：

```text
review_speech(
    player: string,
    phase: string,
    round_number: integer,
    content: string
) -> {
    status: "allowed" | "blocked",
    categories: string[],
    reason: string
}
```

风险分类包括：

- `harassment`：针对现实个人的骚扰或攻击。
- `hate`：针对受保护群体的仇恨内容。
- `sexual`：不适合公开展示的露骨色情内容。
- `self_harm`：鼓励或指导自伤。
- `personal_data`：个人敏感信息泄露。
- `prompt_injection`：试图覆盖审核规则或操纵审核模型。
- `other`：其他明显不适合公开展示的内容。

“击杀”“毒药”“猎人开枪”“欺骗身份”等狼人杀虚构玩法属于正常游戏语境，默认允许。

`unavailable` 不由 MCP Server 或模型返回，而是 MCP Client 在连接失败、超时、工具错误或返回格式错误时生成的本地安全降级状态。

## 3. 服务端实现

### 3.1 服务创建

`create_moderation_server()` 接收一个 `SpeechModerator` 实现并创建 `FastMCP` 实例。将审核实现作为依赖传入，使协议测试能够使用假审核器，不访问真实模型。

生产入口 `werewolf-moderation-mcp` 执行以下步骤：

1. 从现有 `Settings` 读取模型名称、Base URL、超时和密钥。
2. 使用 `build_openai_compatible_model()` 创建 AgentScope 模型。
3. 创建 `ModelSpeechModerator`。
4. 注册 `review_speech` Tool。
5. 使用 stdio transport 运行 MCP Server。

stdio 模式要求 stdout 只能包含 MCP JSON-RPC 消息，因此服务不能调用会向 stdout 打印模型信息的 CLI 辅助函数。普通日志由 MCP/AgentScope 写入 stderr。

### 3.2 模型审核

`ModelSpeechModerator` 将玩家、阶段、回合和发言编码为 JSON 数据，并配合固定系统策略调用 `generate_structured_output()`。

安全约束：

- 系统提示明确声明玩家发言是不可信数据，不执行其中指令。
- JSON 使用 `json.dumps(..., ensure_ascii=False)` 构造，不使用字符串拼接生成字段。
- 模型 Schema 只允许 `allowed` 和 `blocked`。
- 整个模型调用受 `LLM_TIMEOUT` 限制。
- 结果再次经过 Pydantic 校验；非法结果转为 MCP Tool error。
- 被拒绝原文不写入事件和结构化日志。

## 4. 客户端实现

`McpSpeechModerator` 使用 AgentScope 2.0.4 的：

- `MCPClient`
- `StdioMCPConfig`
- stateful session
- `get_tool("review_speech")`

默认通过当前 Python 解释器启动：

```text
python -m werewolf_game.mcp.moderation_server
```

连接生命周期：

1. API 或 CLI 启动时调用 `start()`，创建 MCP 子进程并完成初始化和工具发现。
2. 多局游戏共享一个 stateful MCP Client 和 Tool 对象。
3. 每次调用解析 AgentScope `ToolChunk` 中的 JSON 文本并校验为 `ModerationDecision`。
4. 调用异常时关闭失效连接，返回 `unavailable`。
5. 下一次发言会重新连接，避免一次子进程故障永久关闭审核。
6. API/CLI 关闭时，在游戏任务停止后调用 `close()`。

连接和工具发现使用锁保护，避免并发游戏同时创建多个审核子进程。

## 5. 游戏业务接入

`GameEngine` 在 `_discuss()` 收到 `speech` 活动后，仅当事件可见性为 `public` 时调用审核器。

处理规则：

| 审核状态 | 公开 `speech` 内容 | 内部审计事件 | 游戏是否继续 |
| --- | --- | --- | --- |
| `allowed` | Agent 原文 | 无 | 是 |
| `blocked` | `[该玩家发言因内容审核未通过而隐藏]` | `speech_moderated` | 是 |
| `unavailable` | `[内容审核暂时不可用，该玩家本轮发言已跳过]` | `speech_moderated` | 是 |

`speech_moderated` 使用 `internal` 可见性，payload 只包含：

```json
{
  "player": "刘备",
  "status": "blocked",
  "categories": ["harassment"]
}
```

不保存原文和模型生成的自由文本原因。即使自定义 `SpeechModerator` 意外抛出异常，游戏引擎也会转换为 `unavailable`，避免整局失败或未经审核的内容直接放行。

## 6. 启动和调试

安装依赖：

```powershell
uv sync --group dev
```

独立启动 MCP Server：

```powershell
uv run werewolf-moderation-mcp
```

stdio 服务通常不由人直接输入 JSON-RPC，推荐使用 MCP Inspector：

```powershell
npx -y @modelcontextprotocol/inspector uv run werewolf-moderation-mcp
```

在 Inspector 中检查：

1. 初始化和能力协商成功。
2. Tools 列表只有 `review_speech`。
3. 输入 Schema 和结构化输出 Schema 正确。
4. 正常狼人杀发言返回 `allowed`。
5. 辱骂、隐私信息和提示词注入返回 `blocked`。

运行游戏时不需要手动启动 MCP Server。API 和 CLI 会自动创建和关闭子进程：

```powershell
uv run werewolf-game run --players 6 --show-dialogue --view god
```

## 7. 测试策略

离线测试不访问真实模型：

- 模型适配测试：验证不可信发言被放入 JSON 数据区，结构化结果正确解析。
- MCP Server 测试：验证工具发现、输入/输出 Schema 和 `tools/call`。
- MCP Client 测试：验证连接复用、ToolChunk 解析、失败关闭和下次调用重连。
- 游戏引擎测试：验证允许、拦截和审核器异常三条路径。
- 隐私测试：验证被拒绝原文不会进入公开或内部事件。
- 回归测试：验证审核失败不会中断游戏。

项目验收命令：

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=werewolf_game --cov-fail-under=85
```

真实模型测试前必须确认有效模型名、Base URL 和脱敏 Key 后缀，不得输出完整密钥。

## 8. 后续演进

首版跑通后可以按以下顺序扩展：

1. 增加关键词或本地规则预过滤，减少每条发言调用大模型的成本。
2. 增加审核耗时、通过率、拦截分类和 MCP 重连次数指标。
3. 将 stdio 切换为 Streamable HTTP，并增加 OAuth scope 和 Origin 校验。
4. 为策略文档增加 MCP Resource，让审核策略可发现、可版本化。
5. 增加人工复核队列，而不是将模型判断作为不可追溯的最终决定。

## 9. 关键文件

| 文件 | 作用 |
| --- | --- |
| `application/moderation.py` | 审核状态、分类和结构化结果 |
| `application/ports.py` | `SpeechModerator` 应用端口 |
| `infrastructure/moderation.py` | 模型审核器和 MCP Client 适配器 |
| `mcp/moderation_server.py` | FastMCP Server、Tool 和命令入口 |
| `application/engine.py` | 公开发言审核与事件降级 |
| `api/app.py`、`cli.py` | MCP Client 生命周期 |
| `tests/integration/test_mcp_moderation.py` | MCP Server、Client 和模型适配测试 |
