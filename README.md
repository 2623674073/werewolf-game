# 群雄夜宴 · AI 狼人杀实时观战平台

> 让多个 AI Agent 在一场完整的三国主题狼人杀中自主推理、发言、欺骗与决策，并把全过程实时呈现在可回放的沉浸式观战控制台中。

[![CI](https://github.com/2623674073/werewolf-game/actions/workflows/ci.yml/badge.svg)](https://github.com/2623674073/werewolf-game/actions/workflows/ci.yml)
[![Security](https://github.com/2623674073/werewolf-game/actions/workflows/security.yml/badge.svg)](https://github.com/2623674073/werewolf-game/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/2623674073/werewolf-game/graph/badge.svg)](https://codecov.io/gh/2623674073/werewolf-game)
[![License](https://img.shields.io/github/license/2623674073/werewolf-game)](LICENSE)
[![Release](https://img.shields.io/github/v/release/2623674073/werewolf-game?include_prereleases)](https://github.com/2623674073/werewolf-game/releases)

`v0.3.0` · `AgentScope 2.0.4` · `OpenAI-compatible` · `FastAPI` · `React` · `SSE` · `SQLite` · `MCP`

> 当前是生产化设计的单机、单进程 AI 应用，而不是多租户公网 SaaS。仓库通过确定性 Demo Runtime 提供无模型 Key 的完整体验，真实模型能力必须单独验证。

## 项目介绍

群雄夜宴不是一段简单的多 Agent 对话脚本，而是一套可运行、可观测、可复盘的 AI 社交推理应用。系统会为 6–12 位三国人物随机分配狼人、预言家、女巫、猎人和村民身份，由大模型驱动每位玩家独立思考，并按照夜晚行动、白天讨论、公开投票和胜负判定推进完整对局。

项目既可以作为 AgentScope 2.0、多 Agent 编排和结构化输出的工程实践，也可以用于课堂演示、模型能力观察、OpenAI-compatible 接口联调，以及实时事件驱动前后端的参考实现。

### 为什么不只是一个多 Agent Demo

- 游戏规则、Agent Runtime、持久化和交付接口通过端口解耦，离线 Runtime 与真实模型执行同一套领域流程。
- 正式事件先写入 SQLite 再推送，SSE 通过严格递增序号和 `Last-Event-ID` 恢复一致性。
- 文本增量属于临时传输帧，最终发言才是持久化事实，兼顾实时体验、回放和数据库成本。
- 单个模型调用失败可降级，系统级故障进入稳定终态并只暴露安全错误码。
- MCP 不介入实时主链路，只在终局读取脱敏后的完整卷宗生成可引用证据的结构化复盘。

### 核心体验

| 能力        | 说明                                                                               |
| ----------- | ---------------------------------------------------------------------------------- |
| AI 自主对局 | 每位玩家拥有独立身份、人物性格和上下文，能够自由讨论并完成受 Schema 约束的秘密行动 |
| 沉浸式观战  | 国风棋盘、20 位三国人物立绘、昼夜场景和角色徽记共同呈现 6–12 人对局                |
| 真实流式对话 | AgentScope 直接转发模型生成增量，发言自然出现并保持可读，不使用前端假打字计时器      |
| 实时事件流  | 发言、阶段切换、投票、查验、用药、淘汰和胜负通过 SSE 逐条推送，无需轮询等待        |
| 双视角观察  | 公开视角保护秘密信息；全知视角展示狼人讨论、投票理由、怀疑值和角色技能             |
| 暂停与复盘  | 支持暂停、倍速、事件定位和终局回放，并可按需生成全知视角史官评局                  |
| 稳健降级    | 单个模型调用失败不会拖垮整局；支持超时、有限重试、并发限制、断线补发和安全错误码   |
| 人物演绎    | 20 位武将拥有独立性格、表达强度、句式与语言习惯，粗豪和克制风格均可自然呈现        |
| 史官 MCP    | 终局后按需生成关键转折、阵营得失、玩家评分、MVP 和国风结语                        |
| 对局管理    | 已结束卷宗可经二次确认永久删除，并级联清理完整事件与史官复盘                     |

### 界面预览

![对局大厅：创建游戏与历史对局管理](docs/images/game-lobby.png)

对局大厅提供人数选择、一键开局、状态筛选和历史卷宗入口。

![全知观战：环形席位、身份信息与事件时间线](docs/images/game-spectator.png)

全知视角将玩家状态、角色身份、公开发言和秘密行动统一投射到可暂停、可倍速、可定位的事件时间线上。以上画面由离线确定性对局生成，不依赖真实模型服务。

### 一局游戏如何运行

```mermaid
flowchart LR
    A[创建 6–12 人对局] --> B[随机分配身份与人物]
    B --> C[夜晚秘密行动]
    C --> D[白天公开讨论]
    D --> E[投票与角色技能]
    E --> F{胜负已确定?}
    F -- 否 --> C
    F -- 是 --> G[身份揭晓与终局复盘]
```

## 技术架构

项目采用模块化单体和端口适配架构。领域规则不依赖 AgentScope、FastAPI、SQLAlchemy 或前端框架，模型、数据库和交付接口均通过应用层端口接入，便于测试与替换。

```mermaid
flowchart TB
    UI[React 观战控制台] -->|REST / SSE| API[FastAPI API]
    CLI[CLI] --> APP[GameService / GameEngine]
    API --> APP
    APP --> DOMAIN[Domain Rules & Events]
    APP --> RUNTIME[AgentRuntime Port]
    APP --> REPO[GameRepository Port]
    APP --> REVIEW[GameReviewService]
    RUNTIME --> AS[AgentScope 2.0]
    AS --> LLM[OpenAI-compatible LLM]
    REPO --> DB[(SQLite / SQLAlchemy Async)]
    REVIEW --> MCP[MCP Client / stdio 史官服务]
    MCP --> LLM
    APP --> BROKER[Event Broker]
    BROKER --> API
```

### 技术栈

| 层次         | 技术                                                | 用途                                             |
| ------------ | --------------------------------------------------- | ------------------------------------------------ |
| Agent 与模型 | AgentScope 2.0.4、OpenAI-compatible API、Pydantic 2 | Agent 会话、自由发言、结构化投票和技能决策       |
| 后端应用     | Python 3.12、FastAPI、asyncio                       | 游戏引擎、后台对局任务、REST、SSE 和生命周期管理 |
| 数据持久化   | SQLAlchemy Async、aiosqlite、Alembic                | 游戏状态、玩家快照、事件序列和数据库迁移         |
| 实时与安全   | SSE、Bearer Token、MCP、JSON 日志                   | 断线补发、管理鉴权、终局复盘和可观测性           |
| 前端         | React 19、TypeScript、Vite、TanStack Query、Zustand | 服务状态、事件队列、播放游标和观战界面           |
| 交互与视觉   | Tailwind CSS、Radix UI、Motion                      | 国风主题、无障碍控件和阶段动画                   |
| 工程质量     | uv、ruff、mypy、pytest、Vitest、Playwright          | 依赖管理、静态检查、单元测试和端到端验证         |

### 项目结构

```text
werewolf_game/
├─ src/werewolf_game/
│  ├─ domain/          玩家、角色、规则、行动 Schema 和游戏事件
│  ├─ application/     游戏引擎、任务服务、端口和事件发布
│  ├─ infrastructure/  AgentScope、OpenAI-compatible、SQLite 和日志适配
│  ├─ mcp/             独立的 stdio 终局史官服务
│  └─ api/             FastAPI、Bearer 鉴权、REST、SSE 和 SPA 托管
├─ frontend/           React 实时观战与终局复盘控制台
├─ tests/              单元、应用、基础设施、API 和 E2E 测试
├─ migrations/         Alembic 数据库迁移
└─ docs/               架构与 MCP 实现说明
```

运行中的 Agent 上下文只保存在当前进程。SQLite 保存游戏状态、玩家快照和完整事件；服务重启后，未完成游戏会标记为 `interrupted`，不会恢复模型上下文。更多设计细节见 [架构说明](docs/architecture.md)。

## 运行环境与配置

- Python 3.12
- uv
- Node.js 20+ 与 npm
- Docker Desktop / Docker Engine（推荐体验方式）
- 支持工具调用的 OpenAI-compatible 模型接口（真实模型模式）

## 五分钟离线体验（推荐）

离线模式会执行真实的游戏引擎、SQLite、REST、SSE、回放和史官流程，只把模型 Runtime 替换成确定性实现。界面会显示“离线演示”，不会把它伪装成真实模型能力。

```powershell
Copy-Item .env.example .env

# 生成管理令牌并写入 .env
$token = [Convert]::ToHexString(
  [Security.Cryptography.RandomNumberGenerator]::GetBytes(24)
).ToLower()
# 将 .env 中 APP_API_TOKEN 替换为 $token，并设置 RUNTIME_MODE=demo

docker compose up --build
```

Linux/macOS 可使用：

```bash
cp .env.example .env
openssl rand -hex 24
# 将输出写入 .env 的 APP_API_TOKEN，保持 RUNTIME_MODE=demo
docker compose up --build
```

访问 `http://127.0.0.1:8000`，输入刚生成的管理令牌。容器会以非 root 用户运行、自动执行 Alembic、托管已构建前端，并把 SQLite 保存到命名卷。

停止服务：

```powershell
docker compose down
```

`docker compose down -v` 会永久删除本地游戏数据卷，只有确定不再需要历史对局时才使用。

### 真实模型模式

源码运行时先安装依赖并创建 `.env`：

```powershell
uv sync --group dev
npm ci
Copy-Item .env.example .env
```

编辑 `.env`，至少设置：

```dotenv
RUNTIME_MODE=openai
LLM_API_KEY=your-key
LLM_MODEL_ID=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
APP_API_TOKEN=请替换为至少24位的随机令牌
```

模型服务必须同时支持普通文本、流式 Chat Completions、`tools` 和强制工具选择。默认 `LLM_TRUST_ENV=false`，不会继承系统代理；兼容性边界和验证记录见 [模型兼容性](docs/model-compatibility.md)。

常用配置：

| 环境变量                | 默认值                                   | 说明                       |
| ----------------------- | ---------------------------------------- | -------------------------- |
| `LLM_MODEL_ID`          | 必填                                     | OpenAI-compatible 模型 ID  |
| `LLM_BASE_URL`          | 必填                                     | OpenAI-compatible 接口地址 |
| `LLM_TIMEOUT`           | `60`                                     | 单次模型调用超时（秒）     |
| `LLM_TRUST_ENV`         | `false`                                  | 是否继承系统代理配置       |
| `HISTORIAN_TIMEOUT`     | `600`                                    | 一次史官任务超时（秒）     |
| `DATABASE_URL`          | `sqlite+aiosqlite:///./data/werewolf.db` | SQLite 地址                |
| `CORS_ORIGINS`          | `[]`                                     | JSON 格式的前端来源白名单  |
| `MAX_CONCURRENT_GAMES`  | `4`                                      | 同时运行的游戏数           |
| `MAX_MODEL_CONCURRENCY` | `8`                                      | 同时执行的模型调用数       |
| `MODEL_MAX_RETRIES`     | `2`                                      | 模型调用重试次数           |
| `WEB_DIST_DIR`          | `frontend/dist`                          | FastAPI 托管的前端构建目录 |
| `METRICS_ENABLED`       | `true`                                   | 是否启用受鉴权的指标接口   |
| `MAX_SSE_CONNECTIONS`   | `100`                                    | 单进程最大实时观战连接数   |

密钥不会写入 API 响应或结构化日志。启动时只输出 API Key 后四位。

## 推荐启动方式

项目有两种启动方式：正常使用时采用“构建前端后由 FastAPI 统一托管”，只有修改源码时才使用热更新开发模式。

源码运行适合开发；首次体验优先使用上面的 Docker 方式。

### 第一次启动

在项目根目录依次执行：

```powershell
# 1. 安装 Python 和前端依赖
uv sync --group dev
npm ci

# 2. 创建本地配置文件（已经存在 .env 时跳过）
Copy-Item .env.example .env

# 3. 编辑 .env，至少填写 LLM_API_KEY、LLM_MODEL_ID、LLM_BASE_URL、APP_API_TOKEN
notepad .env

# 4. 初始化或升级数据库
uv run alembic upgrade head

# 5. 构建前端
npm run build

# 6. 启动统一服务
uv run werewolf-server --host 127.0.0.1 --port 8000
```

当终端显示 `Uvicorn running on http://127.0.0.1:8000` 后，浏览器访问 `http://127.0.0.1:8000`，输入 `.env` 中的 `APP_API_TOKEN`。

前端按登录、大厅、对局和复盘路径拆包；构建成功后会生成 `frontend/dist`，FastAPI 只托管该目录中的静态资源。

### 日常启动（推荐）

使用 FastAPI 同时托管前端和 API，不启用热重载。该方式只有一个访问端口，对局过程中不会因为源码变化自动重启，最适合连续运行多局。

如果依赖、数据库结构和前端代码都没有变化，日常只需要执行：

```powershell
uv run werewolf-server --host 127.0.0.1 --port 8000
```

不需要每天重复运行 `uv sync`、`npm ci`、数据库升级或前端构建。

### 拉取代码或修改代码后启动

拉取新版本后，使用下面这组命令最稳妥。没有变化的步骤会很快完成：

```powershell
uv sync --group dev
npm ci
uv run alembic upgrade head
npm run build
uv run werewolf-server --host 127.0.0.1 --port 8000
```

只修改了后端 Python 代码时可以跳过 `npm run build`；只修改了前端代码时必须重新执行 `npm run build`。令牌只保存在当前浏览器标签页的 `sessionStorage` 中。

启动后可用以下命令检查服务：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

如果出现 `[WinError 10048]`，表示端口 `8000` 已被另一个服务占用，和模型、MCP、前端构建都无关。先尝试访问 `http://127.0.0.1:8000`；如果旧服务仍然可用，就不需要再次启动。

需要重启服务时，在旧服务所在终端按 `Ctrl+C`。找不到旧终端时，可在 PowerShell 中查询并停止监听进程：

```powershell
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen
$listener
Stop-Process -Id $listener.OwningProcess -Force
```

确认端口已经释放后再启动：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
uv run werewolf-server --host 127.0.0.1 --port 8000
```

如果不想停止原服务，也可以临时换端口，例如 `--port 8001`，然后访问 `http://127.0.0.1:8001`。

### 前后端开发模式

只有在修改代码时使用：

```powershell
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。Vite 负责前端热更新，FastAPI 监听 `8000` 并只对 `src/` 开启后端热重载。

修改后端源码会重启服务，正在运行的对局将标记为 `interrupted`，前端会短暂显示“正在重连”。因此开发模式不适合长时间演示或验证多局稳定性。

控制台支持创建与启动对局、公开/全知视角、实时对话、暂停与倍速播放、跳到最新和终局复盘，并包含 20 位三国人物立绘、5 类身份视觉标识及昼、夜、终局三套场景。

### 纯命令行运行

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

### 环境诊断

默认只检查配置、数据库、数据目录和前端构建，不消耗模型额度：

```powershell
uv run werewolf-game doctor
```

显式验证真实模型的流式回复和结构化工具调用：

```powershell
uv run werewolf-game doctor --live-model
```

## API

除健康检查外，所有接口要求：

```http
Authorization: Bearer <APP_API_TOKEN>
```

主要接口：

```text
POST /api/v1/games
GET  /api/v1/session
POST /api/v1/games/{id}/start
POST /api/v1/games/{id}/cancel
GET  /api/v1/games
GET  /api/v1/games/{id}?view=public|god
DELETE /api/v1/games/{id}
GET  /api/v1/games/{id}/events?after_seq=0&view=public|god
GET  /api/v1/games/{id}/stream?view=public|god
POST /api/v1/games/{id}/review
GET  /api/v1/games/{id}/review
GET  /health/live
GET  /health/ready
GET  /metrics
```

启用指标后，管理端可携带同一个 Bearer Token 读取 `/metrics`。指标只使用运行模式、操作类型、结果等低基数标签，不包含游戏 ID、玩家名、Token 或模型提示词。

删除接口只接受 `completed`、`draw`、`cancelled`、`interrupted` 和 `failed`
状态。`created`、`running` 或正在生成史官复盘的对局会返回 `409`；删除成功返回
`204`，并永久清除对局、全部公开/私密事件和复盘结果。

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

模型生成中的 `speech_delta` 是不带事件序号的临时 SSE 帧，不写入数据库；发言完成后，系统只保存一条正式 `speech` 事件，其中包含最终全文和相对生成时间轨迹。断线重连以正式事件恢复一致状态，历史回放则使用该轨迹还原原始生成节奏。私密狼人讨论的文本增量只会进入全知视角。

默认 `view=public`，不包含身份、狼人讨论、预言家结果和女巫行动；管理端复盘可显式使用 `view=god`。

## 终局史官 MCP

完整设计、调用链和测试说明见 [终局史官 MCP 实现流程](docs/mcp-game-historian.md)。

实时发言不再经过 MCP 审核，也不会被柔化或替换。正常完成或平局后，终局页面显示
“请史官复盘”。用户点击后，应用层整理全知事件卷宗，通过独立 stdio MCP 的
`generate_game_review` 工具按回合分析并生成结构化总评。

复盘与实时游戏完全解耦；MCP 或复盘模型失败不会改变游戏胜负、对话和历史事件。
失败记录可以重试，成功结果持久化后直接复用。

```powershell
uv run werewolf-historian-mcp
```

使用 Inspector 启动并检查 stdio 服务：

```powershell
npx -y @modelcontextprotocol/inspector uv run werewolf-historian-mcp
```

在 Inspector 中确认只有 `generate_game_review` 工具。输出包含关键转折、胜负因素、
逐人 10 分制评价、MVP 和史官结语，所有评价证据必须引用真实事件序号。stdio 协议要求
标准输出只包含 MCP 消息，因此服务日志不会写入 stdout。

## 开发验收

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=werewolf_game --cov-fail-under=85
npm run lint
npm run typecheck
npm run test:coverage
npm run build
npm run e2e
```

测试默认使用假模型，不访问外部模型服务。真实模型冒烟必须显式设置 `RUN_LIVE_TESTS=1`，并遵守先输出模型名、Base URL 和脱敏 Key 后缀的约定。结构化投票依赖接口支持 `tools` 和 `tool_choice`。

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live -s
```

离线稳定性回归会并发运行 4 局游戏和 20 个 SSE 观察者，并验证事件序号、慢客户端断开与终局收束。设计背景见 [架构说明](docs/architecture.md) 和 [ADR](docs/adr/README.md)。

## 安全、许可证与贡献

- 本项目面向本地或可信内网。管理 Token 可读取全知视角，不应直接暴露到不可信公网。
- 代码和文档使用 [Apache-2.0](LICENSE)；AI 原创立绘与场景使用 [CC BY 4.0](ASSETS.md)。
- 漏洞请按 [安全策略](SECURITY.md) 私下报告，不要公开 Token、数据库或私密事件。
- 开发流程、契约要求与完整验收命令见 [贡献指南](CONTRIBUTING.md)。
- 版本变更见 [Changelog](CHANGELOG.md)。

## 已知边界

- 只能运行一个 Uvicorn worker；内存任务和 SSE Broker 不支持跨进程协调。
- 服务重启会把运行中游戏标记为 `interrupted`，不会恢复 Agent 上下文。
- SQLite 适合单机演示和小规模并发，不提供跨节点高可用。
- 单一管理 Token 不是用户体系或 RBAC；项目不支持匿名观战和真人玩家。
- `v0.x` 阶段的 API 和事件契约可能在 Changelog 说明后调整。
