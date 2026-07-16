# 架构说明

## 边界

`domain` 只包含业务数据和纯规则。`application` 通过 `AgentRuntime` 与 `GameRepository` 协议协调游戏，无法直接访问 AgentScope、SQLAlchemy 或 FastAPI。`infrastructure` 实现这些协议，`api` 只负责输入输出与进程生命周期。

```text
FastAPI / CLI
      │
GameService ── GameEngine ── Domain rules / character personas
      │              │
      │          AgentRuntime ── AgentScope / OpenAI-compatible API
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

## 事件与隐私

事件序号在单局内严格递增。`public` 事件可用于普通观战；`private` 事件包含指定接收者；`internal` 事件只用于管理和诊断。数据库保存全部事件，API 根据 `view` 参数过滤。SSE 订阅在查询历史前建立，实时事件按序号去重，从而覆盖历史查询和实时推送之间的竞态窗口。

## 失败模型

- 单个玩家发言或决策失败由 AgentRuntime 超时、重试并返回空决策，游戏规则负责降级。
- 所有狼人决策失败时从合法目标随机选择；其他技能失败时跳过。
- 初始化、仓储或引擎异常只保存稳定错误码 `game_execution_failed`，不向 API 暴露异常文本。
- 有界 SSE 队列溢出时断开慢客户端，客户端使用 `Last-Event-ID` 重连补发。
- 优雅关闭取消运行任务并将其标记为 `interrupted`。
- 史官任务失败只保存稳定错误码；遗留 `pending` 复盘在重启后标记失败并允许重试。

## 扩展原则

后续前端只依赖 REST 与 SSE 契约。若增加其他模型供应商，实现新的 `AgentRuntime` 即可；若未来需要多进程部署，再将内存任务和 Broker 替换为外部队列，不改变领域规则和 API 事件结构。
