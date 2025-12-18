# 設置基礎映像
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝 gcc, python3-dev, 和 g++ (為 phik 編譯所需)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY api/requirements.txt .

# 安裝依賴
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir redis

# 複製專案程式碼
COPY . .

# 開放埠口
EXPOSE 8000

# 啟動命令
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
