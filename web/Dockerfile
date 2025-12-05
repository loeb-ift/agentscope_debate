# 設置基礎映像
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 複製依賴文件
COPY web/requirements.txt .

# 安裝依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案程式碼
COPY . .

# 開放埠口
EXPOSE 7860

# 啟動命令
CMD ["python", "web/app.py"]
