# Contributing

感谢你改进群雄夜宴。项目优先接受可复现、边界清晰，并且不破坏公开/私密事件隔离的改动。

## 开发流程

1. 从 `main` 创建功能分支，不直接向主分支提交。
2. 使用 `RUNTIME_MODE=demo` 复现问题，除非问题只存在于特定模型服务。
3. 修改 API 后运行 `npm run api:generate` 并提交生成文件。
4. 提交 PR，说明业务影响、兼容性、验证证据和回滚方式。

```powershell
uv sync --group dev
npm ci
uv run alembic upgrade head
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

不要提交 `.env`、数据库、模型请求原文、访问令牌、API Key 或未经授权的素材。真实模型测试必须显式启用，并对日志中的凭据做脱敏。

## 设计边界

- 当前版本是单机单进程应用，SQLite、内存任务与内存 SSE Broker 是有意选择。
- 领域层不得依赖 AgentScope、FastAPI、SQLAlchemy 或前端框架。
- 正式事件必须先持久化再发布；临时流式帧不得占用事件序号。
- 新增私密信息时必须同时覆盖 REST、SSE、历史回放和测试中的视角隔离。
