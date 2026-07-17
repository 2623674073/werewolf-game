# ADR 0003: 单进程 SQLite 模块化单体

- Status: Accepted
- Date: 2026-07-10

## Decision

首个开源版本使用 SQLite WAL、内存任务和内存 SSE Broker，并明确只运行一个 Uvicorn worker。

## Consequences

本地运行和部署成本低，事务与事件顺序易验证；服务重启不会恢复 Agent 上下文，运行局会转为 `interrupted`。多实例部署需要外部数据库、任务队列和消息总线，属于未来独立架构阶段。
