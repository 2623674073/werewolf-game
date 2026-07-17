# ADR 0005: 确定性离线 Runtime

- Status: Accepted
- Date: 2026-07-17

## Decision

通过与 AgentScope Runtime 相同的应用端口提供 `demo` 模式，执行真实游戏规则、事件持久化、SSE 和前端流程，但使用确定性发言与决策。

## Consequences

评审者和 CI 无需模型 Key 即可验证产品。界面和文档必须清楚标识离线模式，不能把其输出作为真实模型能力证据；真实兼容性由显式 live smoke 验证。
