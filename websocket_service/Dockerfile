FROM docker.m.daocloud.io/library/python:3.11-slim
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
