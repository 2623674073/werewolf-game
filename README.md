# werewolf_game

基于 AgentScope 2.0.4 的三国主题狼人杀服务。项目提供 FastAPI、SSE 实时事件流和命令行入口，核心规则不依赖 AgentScope、Web 框架或数据库。

## 架构

```text
src/werewolf_game/
├─ domain/          玩家、角色、规则、行动 Schema 和游戏事件
├─ application/     游戏引擎、任务服务、端口和事件发布
├─ infrastructure/  AgentScope、OpenAI-compatible、SQLite 和日志适配
├─ mcp/             独立的 stdio MCP 服务
├─ api/             FastAPI、Bearer 鉴权、REST 和 SSE
├─ config.py        环境变量配置
└─ cli.py           服务和单局命令行入口
```

运行中的 Agent 上下文只保存在当前进程。SQLite 保存游戏状态、玩家快照和完整事件；服务重启后，未完成游戏会标记为 `interrupted`，不会恢复模型上下文。详细设计见 [docs/architecture.md](docs/architecture.md)。

## 环境

- Python 3.12
- uv
- 支持工具调用的 OpenAI-compatible 模型接口

```powershell
uv sync --group dev
Copy-Item .env.example .env
```

编辑 `.env`，至少设置：

```dotenv
LLM_API_KEY=your-key
LLM_MODEL_ID=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
APP_API_TOKEN=replace-with-at-least-24-characters
```

常用配置：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_MODEL_ID` | 必填 | OpenAI-compatible 模型 ID |
| `LLM_BASE_URL` | 必填 | OpenAI-compatible 接口地址 |
| `LLM_TIMEOUT` | `60` | 单次模型调用超时（秒） |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/werewolf.db` | SQLite 地址 |
| `CORS_ORIGINS` | `[]` | JSON 格式的前端来源白名单 |
| `MAX_CONCURRENT_GAMES` | `4` | 同时运行的游戏数 |
| `MAX_MODEL_CONCURRENCY` | `8` | 同时执行的模型调用数 |
| `MODEL_MAX_RETRIES` | `2` | 模型调用重试次数 |

密钥不会写入 API 响应或结构化日志。启动时只输出 API Key 后四位。

## 数据库与启动

首次运行或升级版本时执行：

```powershell
uv run alembic upgrade head
```

启动 HTTP 服务：

```powershell
uv run werewolf-server --host 127.0.0.1 --port 8000
```

直接运行一局：

```powershell
uv run werewolf-game run --players 6
```

以可读方式显示全部角色对话和私密行动：

```powershell
uv run werewolf-game run --players 6 --show-dialogue --view god
```

只显示公开讨论和公开结果：

```powershell
uv run werewolf-game run --players 6 --show-dialogue --view public
```

## API

除健康检查外，所有接口要求：

```http
Authorization: Bearer <APP_API_TOKEN>
```

主要接口：

```text
POST /api/v1/games
POST /api/v1/games/{id}/start
POST /api/v1/games/{id}/cancel
GET  /api/v1/games
GET  /api/v1/games/{id}?view=public|god
GET  /api/v1/games/{id}/events?after_seq=0&view=public|god
GET  /api/v1/games/{id}/stream?view=public|god
GET  /health/live
GET  /health/ready
```

创建并启动游戏：

```powershell
$headers = @{ Authorization = "Bearer $env:APP_API_TOKEN" }
$game = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/games `
  -Headers $headers `
  -ContentType application/json `
  -Body '{"player_count":6}'

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/games/$($game.id)/start" `
  -Headers $headers
```

SSE 支持 `Last-Event-ID` 断线补发。浏览器原生 `EventSource` 无法设置 Authorization Header，前端应使用支持流式 `fetch` 的 SSE 客户端，不要把令牌放入 URL。

默认 `view=public`，不包含身份、狼人讨论、预言家结果和女巫行动；管理端复盘可显式使用 `view=god`。

## 发言审核 MCP

完整设计、调用链和测试说明见 [发言内容审核 MCP 实现流程](docs/mcp-speech-moderation.md)。

游戏运行时会启动一个独立的 stdio MCP 子进程，并在公开发言写入事件库前调用
`review_speech` 工具。审核服务使用当前 OpenAI-compatible 模型返回结构化结果：

- `allowed`：原文进入公开 `speech` 事件。
- `blocked`：原文不会持久化，公开事件改为固定的审核隐藏提示。
- MCP 或模型不可用：跳过本轮发言但不中断对局，也不会放行未经审核的原文。

狼人杀规则语境中的“击杀”“毒药”“投票”等虚构描述默认允许。被拦截或审核不可用时，
系统另存一条不包含原文的 `internal` 类型 `speech_moderated` 事件。

MCP 服务也可以单独启动，供 MCP Inspector 调试：

```powershell
uv run werewolf-moderation-mcp
```

使用 Inspector 启动并检查 stdio 服务：

```powershell
npx -y @modelcontextprotocol/inspector uv run werewolf-moderation-mcp
```

在 Inspector 中确认只有 `review_speech` 工具，然后分别测试正常游戏发言、辱骂、
个人信息和“忽略审核规则”等提示词注入输入。stdio 协议要求标准输出只包含 MCP 消息，
因此服务日志不会写入 stdout。

## 开发验收

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=werewolf_game --cov-fail-under=85
```

测试默认使用假模型，不访问外部模型服务。真实模型冒烟必须显式设置 `RUN_LIVE_TESTS=1`，并遵守先输出模型名、Base URL 和脱敏 Key 后缀的约定。结构化投票依赖接口支持 `tools` 和 `tool_choice`。
