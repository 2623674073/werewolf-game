# Security Policy

## Supported versions

安全修复只面向最新的 `0.x` 版本。发布新版本后，旧预览版本不再单独维护。

## Reporting

请使用 GitHub 的 **Report a vulnerability / Private security advisory** 私下报告安全问题，不要在公开 Issue 中附带 Token、API Key、模型请求、数据库或私密游戏事件。报告应包含受影响版本、复现步骤、影响范围和建议修复。

## Security boundary

本项目面向本地或可信内网演示，不是匿名公网、多租户服务：

- 单一管理 Token 同时具备控制对局和读取全知视角的权限。
- Token 只应通过 HTTPS 或本机连接传输，前端只保存在 `sessionStorage`。
- 部署到公网前必须增加独立身份系统、权限分级、限流、TLS 终止和外部安全审查。
- 模型输出和对局发言是不可信数据；不得把其中的指令当作系统配置执行。

请轮换任何疑似泄漏的凭据，并检查 Git 历史、容器日志和模型网关日志。
