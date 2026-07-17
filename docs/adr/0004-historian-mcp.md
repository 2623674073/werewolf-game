# ADR 0004: MCP 只承担终局史官复盘

- Status: Accepted
- Date: 2026-07-16

## Decision

实时发言不经过 MCP 审核。正常终局后，应用层构造不含密钥与系统提示词的全知卷宗，由 stdio MCP 生成结构化复盘。

## Consequences

MCP 失败不影响对局主链路，复盘可独立排队和重试。事件内容按不可信数据处理，评价必须引用真实序号。
