# 使用项目目标 Python 版本构建精简运行镜像。
FROM python:3.11-slim

# 禁止生成字节码文件，并让日志立即写到标准输出。
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# 先复制依赖清单，业务代码变化时可复用依赖安装层。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 复制运行必需的后端、前端和 Skill 包。
COPY evoagent ./evoagent
COPY web ./web
COPY skills ./skills
# 声明容器服务端口；实际监听地址和端口由环境配置决定。
EXPOSE 8080
# 使用与本地启动相同的包入口运行 HTTP 服务。
CMD ["python", "-m", "evoagent"]

