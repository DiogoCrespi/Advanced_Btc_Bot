FROM python:3.11

# 从 uv 官方镜像复制 uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/
ENV UV_HTTP_TIMEOUT=1000

WORKDIR /app

# 先复制依赖描述文件以利用缓存
COPY backend/pyproject.toml backend/uv.lock ./backend/

# 安装 Python 依赖
RUN cd backend && uv sync --frozen

# 复制项目源码
COPY . .

EXPOSE 5001

# 启动后端 (Uvicorn)
CMD ["python", "backend/run.py"]