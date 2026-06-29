# 闲鱼助手 Lite

基于 FastAPI + React + MySQL + Redis 的闲鱼多账号自动化系统（轻量版）。

## 功能

- **账号管理** — 多账号 Cookie 管理、状态切换
- **商品管理** — 查看商品列表
- **自动回复** — 关键词匹配回复，支持按商品绑定
- **确认收货消息** — 支持按商品维度配置不同消息内容
- **订单管理** — 订单列表与状态跟踪
- **数据统计** — 概览与每日统计
- **WebSocket 长连接** — 实时接收闲鱼消息
- **定时任务** — Cookie 续期、拉取订单、每日统计汇总

## 快速启动

\\\ash
docker compose up -d
\\\

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:8080 |
| 后端 API | http://localhost:8000 |
| WebSocket | 端口 8001 |

默认管理员账号：\dmin\ / \dmin123\

## 项目结构

\\\
xianyu-lite/
├── backend/            # FastAPI 后端 (HTTP API)
│   └── app/
│       ├── api/        # API 路由
│       ├── models/     # 数据模型
│       └── utils/      # 闲鱼协议工具
├── websocket_service/  # WebSocket 长连接服务
├── scheduler/          # APScheduler 定时任务
├── frontend/           # React 前端 (Neumorphism 风格)
└── docker/             # Docker 配置
\\\

## 设计风格

Neumorphism（新拟物风格），浅色柔和背景，通过多重阴影营造浮雕质感。
