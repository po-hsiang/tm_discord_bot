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

# 安裝 Poetry
RUN pip install poetry

# 設置工作目錄為 /app
WORKDIR /app

# 複製只有 pyproject.toml 和 poetry.lock 的 Python 依賴文件
# 這允許 Docker 利用緩存，如果這些文件沒有變化，則不需重新安裝依賴
COPY pyproject.toml poetry.lock* /app/

# 安裝依賴，不建立虛擬環境
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# 複製應用程序的其餘部分到容器中
COPY . /app

# 當容器啟動時運行 Python 應用程序
CMD ["python", "./tm_discord_bot/scripts/main.py"]
