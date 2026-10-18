# EvoAgent V2

V2 是从单 Prompt 基线到完整 EvoAgent 之间的第二个复现版本。它保留 V1，并加入固定、可测量的多角色协作：

```text
Lead 规划
  ├─ Security Worker
  └─ Correctness/Reliability Worker
                 ↓
              Critic
                 ↓
          Lead 最终综合
                 ↓
        确定性 Diff 证据门禁
```

它刻意不包含自主工具循环、Memory、Skill、自进化、自动修复、Redis 或 PostgreSQL。这些属于后续版本。

## V2 与 V1 的区别

| 能力 | baseline | collaborative |
| --- | --- | --- |
| 模型调用 | 1 次 | 固定 5 次 |
| 专业分工 | 无 | 安全 + 正确性/可靠性 |
| Critic | 无 | 一次盲审 |
| Diff 证据门禁 | 有 | 有 |
| 角色轨迹与 Token | 有 | 有 |

两个模式使用同一套 GitHub、SQLite、前端和 Finding Gate，可以直接运行对照实验。

## 启动

要求 Python 3.10+，不需要安装第三方依赖。

```bash
cd ~/Desktop/EvoAgent_v2
cp .env.example .env
# 编辑 .env，填写模型地址、API Key 和模型名
./start.sh
```

打开 <http://127.0.0.1:8083>。

模型必须兼容 OpenAI Chat Completions。优先填写完整的 `EVOAGENT_V2_LLM_CHAT_COMPLETIONS_URL`；如果只填写 Base URL，程序会追加 `/chat/completions`。

GitHub Token 对公开 PR 不是必需的，但无 Token 的 API 速率限制更低。私有仓库和评论回写需要 fine-grained token。

## 使用方式

网页提供三种操作：

1. `collaborative`：运行 V2 固定五次调用；
2. `baseline`：运行 V1 风格的一次调用；
3. `V1 / V2 对照`：针对同一 PR 同时创建两个模式的任务。

任务详情包括：

- 最终 Finding；
- 被证据门禁拒绝的问题；
- 每个角色的状态、耗时和 Token；
- 总调用次数、总模型耗时和 Diff 大小；
- GitHub 评论投递状态。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 配置与 TLS 状态 |
| `GET` | `/api/tasks` | 最近任务 |
| `GET` | `/api/tasks/{id}` | 报告、指标和角色轨迹 |
| `POST` | `/api/reviews/from-pr` | 创建 baseline 或 collaborative 审查 |
| `POST` | `/api/reviews/compare` | 创建同一 PR 的 V1/V2 对照 |
| `POST` | `/webhooks/github` | 签名验证后的 PR Webhook，默认运行 collaborative |

示例：

```bash
curl -X POST http://127.0.0.1:8083/api/reviews/from-pr \
  -H 'Content-Type: application/json' \
  -d '{"pull_request_url":"https://github.com/owner/repo/pull/42","mode":"collaborative"}'
```

## 测试

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py evoagent_v2/*.py
node --check static/app.js
sh -n start.sh
```

测试不会访问真实 GitHub 或模型服务。

## 重要边界

- Finding 只有在文件路径、添加行号和 evidence 都能在 Diff 中验证时才会发布。
- 超出大小上限的 Diff 会明确失败，不会静默截断。
- 模型审查成功与 GitHub 评论投递分开记录；评论失败不会删除报告。
- `.env`、数据库和缓存已被忽略，分享时仍应使用白名单打包。
- 默认仅监听 `127.0.0.1`。接收公网 Webhook 时，应通过反向代理只公开 `/webhooks/github`，不要把整个管理页面直接暴露到公网。
- PR Diff 会发送到你配置的模型服务，请只审查允许该服务处理的仓库。

## V3 入口

完成 V1/V2 同集评测后，V3 再引入 Repository Tools、受限工具循环、步骤/Token/时间预算和 Checkpoint。不要在没有对照结果前继续堆叠复杂度。
