#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

pull_with_retry() {
  image="$1"
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "$image 已存在，跳过拉取"
    return 0
  fi
  attempt=1
  while [ "$attempt" -le 5 ]; do
    if docker pull "$image"; then
      return 0
    fi
    echo "拉取 $image 失败，5 秒后重试：$attempt/5"
    sleep 5
    attempt=$((attempt + 1))
  done
  echo "拉取 $image 失败"
  return 1
}

echo "== 商品管理云端验证：预拉基础镜像 =="
pull_with_retry docker.m.daocloud.io/library/python:3.11-slim
pull_with_retry docker.m.daocloud.io/library/node:20-alpine
pull_with_retry docker.m.daocloud.io/library/nginx:alpine

echo "== 商品管理云端验证：构建后端测试镜像 =="
docker compose build backend

echo "== 商品管理云端验证：后端规则测试 =="
docker compose run --rm --no-deps backend sh -lc "python -m pip install -q -r requirements-dev.txt && python -m pytest tests -q"

echo "== 商品管理云端验证：构建并启动服务 =="
docker compose up -d --build

echo "== 商品管理云端验证：服务状态 =="
docker compose ps

echo "== 商品管理云端验证：后端健康检查 =="
i=1
while [ "$i" -le 30 ]; do
  if docker compose exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read().decode())"; then
    break
  fi
  sleep 2
  i=$((i + 1))
done

if [ "$i" -gt 30 ]; then
  echo "后端健康检查失败，请查看 docker compose logs backend"
  exit 1
fi

echo "== 商品管理云端验证完成 =="
echo "继续按 docs/product-management-cloud-checklist.md 在浏览器完成人工流程验收。"
