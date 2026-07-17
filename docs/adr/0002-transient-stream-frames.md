# ADR 0002: 流式增量不进入持久化事件序列

- Status: Accepted
- Date: 2026-07-16

## Decision

模型生成中的 `speech_delta` 只经过内存 Broker，不分配序号；发言完成后持久化唯一 `speech` 事实，并保存紧凑时间轨迹。

## Consequences

避免数据库被 token 级事件放大，重连仍能依赖最终全文恢复一致性。断线期间可能错过临时增量，但不会丢失完成后的业务事实。
