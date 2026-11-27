# EvoAgent 本地运行

解压后进入包含 `requirements.txt` 的 `EvoAgent` 目录。建议使用 Python 3.11。

## Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## macOS / Linux

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

已有 `.env` 时，保留原文件并按需修改。首次运行使用本机 SQLite，无需先安装 PostgreSQL 或 Redis。

## 配置模型并启动

打开 `.env`，换成自己的模型配置。例如使用 DeepSeek 时，修改这两项：

```dotenv
EVOAGENT_LLM_PROVIDER=deepseek
EVOAGENT_DEEPSEEK_API_KEY=<填你自己的密钥>
```

也可使用 OpenAI 兼容服务，配置 `EVOAGENT_LLM_PROVIDER=custom`、`EVOAGENT_LLM_BASE_URL`、`EVOAGENT_LLM_API_KEY` 和 `EVOAGENT_LLM_MODEL`。未配置模型时，可以启动服务和打开管理台，模型审查需要先配置模型。

- Windows 运行 `.\.venv\Scripts\python.exe -m evoagent`。
- macOS 或 Linux 运行 `.venv/bin/python -m evoagent`。

打开 `http://127.0.0.1:8080/`。可先选择「手动提交 Diff」验证模型审查，再按需配置 GitHub 接入。

