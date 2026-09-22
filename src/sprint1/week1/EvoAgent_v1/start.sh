#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  echo "未找到 .env。请先执行：cp .env.example .env，并填写其中的配置。"
  exit 1
fi

exec python3 server.py
