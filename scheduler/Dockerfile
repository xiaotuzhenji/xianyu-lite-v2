FROM python:3.11-slim
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "app.main"]
