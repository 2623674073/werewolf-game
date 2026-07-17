# ADR 0001: 使用 SSE 推送观战事件

- Status: Accepted
- Date: 2026-07-15

## Decision

REST 提供最终快照，SSE 提供服务端到浏览器的增量事件；客户端使用 `Last-Event-ID` 从 SQLite 补发断线期间的正式事件。

## Consequences

单向观战不需要 WebSocket 的双向协议复杂度。SSE 客户端必须支持 Bearer Header、去重、重连和合法注释心跳。未来加入真人交互时应重新评估 WebSocket，而不是在当前协议中模拟双向消息。
