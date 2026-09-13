# EvoPromptReview

一个不使用 Agent 技术的 GitHub PR 审查服务。每个 PR 的路径固定为：

```text
GitHub PR URL / Webhook
        ↓
GitHub API 获取最新 Diff
        ↓
一次 OpenAI-compatible Chat Completions API 调用
        ↓
JSON 解析、字段校验、SQLite 保存
        ↓
网页报告（可选：回写 GitHub PR 评论）
```

它不包含 Lead/Worker/Critic、工具调用循环、任务规划、记忆、Skill 或 Agent Runtime。

## 给试用者的快速启动

```bash
cd EvoPromptReview-tryout
cp .env.example .env
# 用编辑器打开 .env，填写自己的 GitHub Token、Webhook Secret、LLM API 地址 / Key / 模型
./start.sh
```

浏览器打开 `http://127.0.0.1:8082`。首次试用只需在网页中粘贴一个自己有权限访问的 GitHub PR 链接，再点击“开始一次 API 审查”。

要求：macOS、Linux 或 Windows 的 WSL，并已安装 Python 3.10+。本项目只使用 Python 标准库，不需要安装第三方依赖。

### `.env` 必填项

| 配置项 | 用途 |
| --- | --- |
| `PROMPT_REVIEW_GITHUB_TOKEN` | 读取私有或公开仓库的 PR 和 Diff。建议使用 GitHub fine-grained token，只授予目标仓库的 Metadata / Pull requests 读取权限。 |
| `PROMPT_REVIEW_GITHUB_WEBHOOK_SECRET` | 自动触发时用来验证 GitHub 请求；手动粘贴 PR 链接时仍建议填写一个随机值。 |
| `PROMPT_REVIEW_LLM_BASE_URL` | OpenAI-compatible Chat Completions 服务地址。 |
| `PROMPT_REVIEW_LLM_API_KEY` | 对应大模型服务的密钥。 |
| `PROMPT_REVIEW_LLM_MODEL` | 要使用的模型名称。 |

默认只在本机监听，不会公开网页；`PROMPT_REVIEW_AUTO_POST_REVIEW=false` 时也不会向 GitHub PR 发送评论。

## GitHub 自动触发

将公网 HTTPS 地址加上 `/webhooks/github` 配置到仓库 Webhook，订阅 **Pull requests**。也可在网页“绑定 GitHub 仓库”填写 `owner/repository` 和公网地址，由系统调用 GitHub API 创建该 Webhook；Token 需要对应仓库的 Webhooks 管理权限。系统只处理 `opened`、`reopened`、`synchronize`，并校验 `X-Hub-Signature-256`。每个有效事件创建一个后台任务；GitHub Diff 和 PR 内容会发送到你配置的大模型服务用于审查。

## API

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| `GET` | `/api/health` | 查看模型、GitHub、Webhook 配置状态 |
| `POST` | `/api/reviews/from-pr` | 从 PR 链接创建审查任务 |
| `POST` | `/api/github/connect` | 为仓库创建 Pull Request Webhook |
| `GET` | `/api/tasks` | 任务列表 |
| `GET` | `/api/tasks/{id}` | 任务及结构化报告 |
| `POST` | `/webhooks/github` | GitHub Pull Request Webhook |

`PROMPT_REVIEW_AUTO_POST_REVIEW=true` 时，成功报告会作为 PR 评论发布；默认关闭。

## 分享前的安全说明

- 不要把填写过的 `.env`、`*.db` 或含有令牌的截图放进压缩包或 Git 仓库。
- PR 的 Diff 会被发送到你配置的大模型服务；只对允许该服务处理的仓库启用审查。
- 自动 Webhook 需要稳定的公网 HTTPS 地址。试用阶段直接在网页粘贴 PR 链接即可，无需配置 Webhook。
