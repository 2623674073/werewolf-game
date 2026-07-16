# 终局史官 MCP

## 业务定位

史官 MCP 是终局后的按需分析能力，不参与实时发言、角色行动和胜负判定。游戏正常完成
或平局后，用户可以在终局页面发起复盘；失败不会影响已经完成的对局。

```text
用户点击“请史官复盘”
        │
        ▼
GameReviewService 校验终局并读取全知事件
        │
        ▼
构造不含密钥、数据库连接和系统提示词的 GameDossier
        │
        ▼
McpGameHistorian ── stdio ── generate_game_review
        │
        ▼
按回合归纳 ── 最终结构化总评
        │
        ▼
game_reviews 持久化 ── REST 轮询 ── React 复盘抽屉
```

## Tool 契约

`generate_game_review(dossier)` 接收游戏 ID、胜方、玩家最终身份与存活状态，以及严格
按序号排列的公开和私密事件。输出包括标题、总体总结、2–5 个关键转折、胜负因素、逐人
评价、0–10 分评分、MVP 和史官结语。

事件文本始终作为不可信数据处理。每项关键转折和玩家评价必须引用真实事件序号；应用
会再次校验玩家覆盖、MVP 和证据引用，非法结果将任务标记为失败。

## 长对局处理

MCP Server 先按照回合对事件分组，每回合通过结构化输出生成纪要，再使用全部回合纪要
完成最终综合评价。这样可以覆盖最长 12 人、10 回合对局，并降低单次上下文过大的风险。

## 状态与恢复

- `pending`：任务已创建或排队。
- `completed`：结构化结果已持久化，后续请求直接复用。
- `failed`：MCP、模型或校验失败，可以重新生成。

服务关闭会将活动任务标记为 `service_shutdown`；启动时遗留的 `pending` 记录标记为
`service_restarted`。异常文本不会写入 API 响应。

## 独立调试

```powershell
uv run werewolf-historian-mcp
npx -y @modelcontextprotocol/inspector uv run werewolf-historian-mcp
```

Inspector 中应只出现 `generate_game_review`。stdio 标准输出只用于 MCP 消息，日志写入
标准错误。
