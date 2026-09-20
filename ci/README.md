# 可启用的 GitHub Actions 模板

`verify.yml` 是完整验证工作流模板，尚未放入 `.github/workflows/`，所以当前不会自动运行。

首次发布时，现有 GitHub OAuth 登录缺少 `workflow` 权限，GitHub 拒绝创建工作流。代码和文档已正常上传；没有通过更改账户权限来绕过此限制，也没有把本地测试冒充云端 CI。

仓库所有者之后可通过有相应权限的 GitHub 网页或 Git 凭据，将该文件复制为 `.github/workflows/verify.yml` 并提交。启用前检查私有仓库 Actions 配额与权限。

模板只使用固定提交的官方 Actions，权限为 `contents: read`，在 Ubuntu runner 运行代码扫描、组件测试、九协议隔离验收、客户端策略实验、文档构建，并保存脱敏报告。它不包含服务器 SSH、DNS token、部署密钥或生产发布步骤。

本地等效测试入口见 [证据页](../docs/evidence.md)。云端首次执行仍需检查 runner 的 Docker/网络环境，不能假定已经通过。
