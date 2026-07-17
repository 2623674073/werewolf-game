# 架构说明

## 边界

`domain` 只包含业务数据和纯规则。`application` 通过 `AgentRuntime` 与 `GameRepository` 协议协调游戏，无法直接访问 AgentScope、SQLAlchemy 或 FastAPI。`infrastructure` 实现这些协议，`api` 只负责输入输出与进程生命周期。

```text
FastAPI / CLI
      │
GameService ── GameEngine ── Domain rules / character personas
      │              │
      │          AgentRuntime ─┬─ AgentScope / OpenAI-compatible API
      │                        └─ deterministic Demo Runtime
      │
SQLite repository ── GameReviewService
      │                    │
   SQLite             MCP Client ── stdio historian server ── LLM
```

## 对局生命周期

1. `POST /games` 创建 `created` 记录，不调用模型。
2. `POST /games/{id}/start` 创建受并发限制的后台任务。
3. 引擎分配身份、建立 Agent 会话并依次执行夜晚和白天阶段。
4. 每次业务变化先持久化，再通过进程内 Broker 推送事件。
5. 胜负、平局、取消或异常进入终态，释放 Agent 会话并关闭 SSE。
6. 服务启动时将数据库内遗留的 `running` 游戏标记为 `interrupted`。
7. 正常终局后，用户可按需创建独立史官任务；复盘不改变游戏状态或 SSE 生命周期。
8. 终止状态对局可由管理端永久删除；游戏、事件和复盘通过数据库外键在同一事务中级联清理，复盘创建与删除由按局锁串行化。

## 事件与隐私

事件序号在单局内严格递增。`public` 事件可用于普通观战；`private` 事件包含指定接收者；`internal` 事件只用于管理和诊断。数据库保存全部正式事件，API 根据 `view` 参数过滤。SSE 订阅在查询历史前建立，实时事件按序号去重，从而覆盖历史查询和实时推送之间的竞态窗口。

普通发言使用 AgentScope `reply_stream()`。生成中的 `speech_delta` 仅作为无序号临时帧经过内存 Broker，不持久化，也不推进 `Last-Event-ID`；完成后的 `speech` 是唯一事实来源，并在 JSON payload 中保存全文和紧凑时间轨迹。结构化投票与技能决策使用独立的非流式模型。客户端实时跟随真实增量，历史重新播放才按保存的时间戳与轨迹调度。

## 失败模型

- 单个玩家发言或决策失败由 AgentRuntime 超时、重试并返回空决策，游戏规则负责降级。
- 所有狼人决策失败时从合法目标随机选择；其他技能失败时跳过。
- 初始化、仓储或引擎异常只保存稳定错误码 `game_execution_failed`，不向 API 暴露异常文本。
- 有界 SSE 队列溢出时断开慢客户端，客户端使用 `Last-Event-ID` 重连补发。
- 优雅关闭取消运行任务并将其标记为 `interrupted`。
- 史官任务失败只保存稳定错误码；遗留 `pending` 复盘在重启后标记失败并允许重试。

## 扩展原则

后续前端只依赖 REST 与 SSE 契约。若增加其他模型供应商，实现新的 `AgentRuntime` 即可；若未来需要多进程部署，再将内存任务和 Broker 替换为外部队列，不改变领域规则和 API 事件结构。

## 部署与可观测性

Docker 镜像在构建期编译前端，运行时只包含 Python 环境、静态产物和 Alembic migrations。容器以非 root 用户和单 Uvicorn worker 运行；启动脚本先升级数据库，再启动 API。Compose 只白名单传递必要配置，数据目录使用独立卷。

Prometheus 指标覆盖活跃对局、SSE 连接、模型调用、重试结果和史官任务。标签只描述操作和结果，不包含游戏 ID、玩家或请求文本。`/health/ready` 只反映数据库可用性，外部模型能力由 `werewolf-game doctor --live-model` 显式检查，避免上游模型波动造成服务反复摘流。

公共事件 Schema 以 `type` 为 discriminator，将事件类型与对应 payload 绑定。临时流式帧使用独立判别联合，不进入正式事件列表。
