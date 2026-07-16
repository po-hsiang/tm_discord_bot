# 使用官方 Python 3.8 映像作為基礎映像
FROM python:3.8-slim

# 更新軟件包列表
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安裝 uv（從官方映像複製執行檔，版本與本機開發環境一致）
COPY --from=ghcr.io/astral-sh/uv:0.9.29 /uv /uvx /bin/

# uv 設定：直接使用映像內建的 Python 3.8（不另行下載）、預先編譯 bytecode 加速啟動
# PYTHONUNBUFFERED：print 即時寫出，docker logs 才看得到最新訊息
ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# 設置工作目錄為 /app
WORKDIR /app

# 複製只有相依定義與 lock 的檔案
# 這允許 Docker 利用緩存，如果這些文件沒有變化，則不需重新安裝依賴
COPY pyproject.toml uv.lock .python-version /app/

# 依 lock 檔安裝相依（建立 /app/.venv，--frozen 確保與 uv.lock 完全一致）
RUN uv sync --frozen

# 複製應用程序的其餘部分到容器中
COPY . /app

# 讓容器直接使用 venv 內的 Python
ENV PATH="/app/.venv/bin:$PATH"

# 當容器啟動時運行 Python 應用程序
CMD ["python", "./tm_discord_bot/scripts/main.py"]
