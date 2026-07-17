# 离线稳定性回归

稳定性测试不调用外部模型，目标是验证应用自身的并发、事件顺序和资源边界，而不是宣称模型吞吐能力。

## 场景

- 同一进程并发启动 4 局 6 人游戏。
- 每局预先连接 5 个 SSE 观察者，共 20 条订阅。
- 公开观察者只能接收公开事件，全知观察者可接收私密事件。
- 每条正式时间线必须严格递增且无重复，并以 `game_finished` 收束。
- 有界队列溢出时断开慢客户端，客户端随后可用 `Last-Event-ID` 从数据库恢复。

## 执行

```powershell
uv run pytest tests/stability -q
```

该测试使用真实 SQLite Async 仓储、`GameService`、`GameEngine`、事件 Broker 和确定性 Demo Runtime。外部模型延迟、模型网关容量和真实网络抖动不在这个离线结果的覆盖范围内，应通过显式 live smoke 和部署环境压测单独评估。
