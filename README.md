# 闲鱼助手 Lite v2

一个面向闲鱼自动发货场景的轻量化多账号管理系统。  
项目目标不是做“大而全”的 ERP，而是保留最核心、最实用、最容易部署的能力：

- 多账号管理
- 商品管理
- 自动回复
- 按商品维度配置确认收货后回复
- 订单与发货配置
- 基础统计
- 定时任务
- 登录状态保持
- 商品上架

前端采用轻量的 Neumorphism 风格，适合中小卖家或个人卖家快速部署使用。

---

## 1. 当前状态

这个版本已经完成并验证过以下关键链路：

- 账号可通过网页扫码登录接入
- 登录状态可持续维护
- 商品可创建、编辑、同步
- 商品图片可上传并参与上架
- 草稿商品可自动上架到闲鱼
- 自动上架已适配当前闲鱼网页发布页
- 确认收货后的回复支持按商品配置内容
- 基础统计、订单同步、定时任务可运行

最近已确认修复的两个关键问题：

1. 发布任务卡住在 `publishing` 时，可自动释放重试
2. 闲鱼新版发布页没有独立标题输入框时，系统会自动改为把“标题 + 描述”写入描述编辑器，并识别 `item?id=...` 的成功详情页

---

## 2. 适用场景

适合：

- 闲鱼数字商品 / 虚拟资料 / 轻交付商品
- 多账号统一管理
- 需要自动回复与自动发货的卖家
- 想用 Docker 快速部署的人

不适合：

- 追求特别复杂的企业级流程
- 需要大量财务、仓储、售后工单能力
- 需要强对抗平台频繁风控变化的重度自动化场景

---

## 3. 核心功能

### 3.1 账号管理

- 支持多账号管理
- 支持扫码登录
- 支持 Cookie / 登录状态维护
- 支持查看账号在线状态
- 支持删除和更新账号

### 3.2 商品管理

- 支持商品列表查看
- 支持新建商品
- 支持编辑商品标题、价格、描述
- 支持上传商品图片
- 支持同步账号下已存在商品
- 支持草稿商品自动上架

### 3.3 自动回复

- 支持默认回复
- 支持关键词回复
- 支持商品维度绑定回复规则

### 3.4 确认收货后回复

- 支持按账号配置
- 支持按具体商品覆盖配置
- 可以做到“同一个账号，不同商品发送不同内容”

### 3.5 发货配置

- 支持按账号 / 商品配置发货内容
- 支持订单发货日志查看
- 支持手动触发发货

### 3.6 订单与统计

- 支持订单同步
- 支持订单列表查看
- 支持概览统计
- 支持按天统计

### 3.7 定时任务

- 定时同步订单
- 定时检查 WebSocket 连接状态
- 定时统计

---

## 4. 技术架构

### 4.1 技术栈

后端：

- FastAPI
- SQLAlchemy Async
- MySQL
- Redis
- Playwright
- APScheduler
- WebSocket

前端：

- React
- TypeScript
- Vite
- Zustand
- Axios

部署：

- Docker Compose

### 4.2 服务组成

项目默认包含 6 个服务：

- `frontend`：前端页面，端口 `8080`
- `backend`：HTTP API，端口 `8000`
- `websocket`：闲鱼消息长连接服务，端口 `8001`
- `scheduler`：定时任务服务
- `mysql`：数据库，宿主机端口 `3307`
- `redis`：缓存与状态存储

---

## 5. 目录结构

```text
xianyu-lite-v2/
├─ backend/                 # FastAPI 后端
│  ├─ app/
│  │  ├─ api/               # API 路由
│  │  ├─ models/            # 数据模型
│  │  ├─ services/          # 核心业务服务
│  │  ├─ utils/             # 工具函数
│  │  └─ main.py            # 后端入口
│  ├─ Dockerfile
│  └─ requirements.txt
├─ frontend/                # React 前端
│  ├─ src/
│  ├─ public/
│  ├─ Dockerfile
│  └─ nginx.conf
├─ websocket_service/       # 闲鱼 WebSocket 接入服务
├─ scheduler/               # 定时任务服务
├─ docker/                  # 附加部署配置
├─ docker-compose.yml       # 一键部署入口
└─ README.md
```

---

## 6. 快速开始

### 6.1 环境要求

推荐环境：

- Docker
- Docker Compose
- Linux 服务器 / 本地 Linux / WSL2

如果你只是部署使用，不需要本地安装 Python、Node、MySQL。

### 6.2 启动

在项目根目录执行：

```bash
docker compose up -d
```

首次启动会自动构建镜像。

### 6.3 访问地址

默认端口如下：

- 前端：`http://localhost:8080`
- 后端 API：`http://localhost:8000`
- WebSocket 服务：`ws://localhost:8001`
- MySQL：`localhost:3307`

如果你使用了 Nginx 反代，也可以把前端入口映射到例如：

- `http://服务器IP:9000/dashboard`

### 6.4 默认管理员账号

- 用户名：`admin`
- 密码：`admin123`

---

## 7. Docker Compose 说明

当前 `docker-compose.yml` 使用如下默认配置：

### MySQL

- 数据库名：`xianyu_lite`
- 用户名：`xianyu`
- 密码：`xianyu123`
- Root 密码：`root123`

### Backend

挂载：

- `./backend/app:/app/app`
- `backend_uploads:/app/uploads`

这意味着：

- 后端代码可热更新
- 上传图片会保存在 Docker volume 中

### Scheduler

使用数据库连接：

`mysql+aiomysql://xianyu:xianyu123@mysql:3306/xianyu_lite?charset=utf8mb4`

### WebSocket

默认连接：

`wss://wss-goofish.dingtalk.com/`

---

## 8. 登录与账号接入

### 8.1 推荐方式：网页扫码登录

当前版本已经做了网页内扫码接入，比手填 Cookie 简单很多。

基本流程：

1. 登录后台
2. 进入账号管理
3. 点击生成二维码
4. 使用闲鱼 / 淘宝相关客户端扫码
5. 等待系统轮询登录结果
6. 登录成功后自动保存账号 Cookie

### 8.2 登录状态保持

系统会尽量复用已保存的 Cookie。

但要注意：

- 平台风控可能导致 Cookie 失效
- 长时间不活跃可能掉线
- 账号异常登录也可能触发失效

如果失效：

- 重新扫码登录即可

---

## 9. 商品管理

### 9.1 商品字段

当前商品主要包含：

- 账号 ID
- 商品标题
- 价格
- 商品描述
- 图片列表
- 商品状态
- 发布状态
- 发布错误信息
- 已发布商品 URL

### 9.2 标题限制

闲鱼平台标题限制为 **30 个字**。

当前发布逻辑会自动截断：

- 超过 30 字时，仅取前 30 字

建议你在前台录入时就控制好长度，避免信息被截断。

### 9.3 图片

支持：

- 本地上传图片
- 商品图片随上架流程一起提交

当前实际上架流程已验证：

- 可上传 3 张以上图片
- 图片会参与自动发布

---

## 10. 商品上架能力

### 10.1 当前上架方式

项目使用 **Playwright 浏览器自动化** 上架商品到闲鱼网页端。

核心思路：

1. 注入账号 Cookie
2. 访问 `goofish` 首页建立会话
3. 访问淘宝登录页同步登录态
4. 进入闲鱼发布页
5. 自动填写价格、描述、图片
6. 点击发布
7. 跳转到商品详情页后判定发布成功

### 10.2 已适配的闲鱼网页发布页特征

本项目已经适配当前真实页面：

- 页面没有独立标题输入框
- 标题内容会合并到描述编辑器
- 描述输入区是 `contenteditable`
- 价格框使用 `placeholder="0.00"`
- 发布成功后会跳到 `https://www.goofish.com/item?id=...`

### 10.3 已验证的发布结果

已验证成功发布的商品示例：

- 商品 ID：`1062879541600`

### 10.4 当前已知限制

自动上架不是“永远稳定不变”的接口能力，而是浏览器自动化，所以会受闲鱼页面变动影响。

主要风险：

- 平台页面 DOM 改版
- 登录态失效
- 风控弹窗 / 验证
- 某些分类网页端不支持发布
- 特定商品内容触发审核或拦截

如果未来再次失败，优先排查：

1. Cookie 是否失效
2. 发布页 DOM 是否变化
3. 是否出现滑块 / 二次验证
4. 是否点击发布后进入了详情页但系统没识别

---

## 11. 自动回复与确认收货回复

### 11.1 默认回复

接口前缀：

- `/api/v1/default-replies`

用于给账号设置统一兜底回复。

### 11.2 关键词回复

接口前缀：

- `/api/v1/keywords`

用于配置关键词命中后的自动回复。

### 11.3 确认收货后回复

接口前缀：

- `/api/v1/confirm-receipt`

### 11.4 按商品配置确认收货内容

这是这套系统和原始按账号统一回复相比更重要的改进点之一。

支持：

- 同一账号下
- 针对不同商品
- 配置不同确认收货后消息

也就是说：

- 商品 A 确认收货后发内容 A
- 商品 B 确认收货后发内容 B

而不是只能按账号发一套固定文案。

---

## 12. 发货配置

接口前缀：

- `/api/v1/delivery`

主要用途：

- 给不同账号 / 商品配置发货内容
- 查看发货记录
- 手动触发发货

适合数字商品、网盘链接、资料文本、兑换码等轻交付场景。

---

## 13. 订单与统计

### 13.1 订单

接口前缀：

- `/api/v1/orders`

能力包括：

- 同步订单
- 查看订单列表
- 查看订单状态

### 13.2 统计

接口前缀：

- `/api/v1/statistics`

当前支持：

- 概览统计
- 每日统计

概览中可看到：

- 总账号数
- 总商品数
- 总订单数
- 今日订单数
- 周消息数
- 周回复数
- 周订单金额

---

## 14. 主要接口一览

### 14.1 认证

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### 14.2 账号

- `GET /api/v1/accounts`
- `POST /api/v1/accounts`
- `PUT /api/v1/accounts/{account_id}`
- `DELETE /api/v1/accounts/{account_id}`

### 14.3 二维码登录

- `POST /api/v1/qr-login/generate`
- `GET /api/v1/qr-login/status/{session_id}`
- `POST /api/v1/qr-login/poll/{session_id}`

### 14.4 商品

- `GET /api/v1/items`
- `POST /api/v1/items`
- `PUT /api/v1/items/{item_id}`
- `DELETE /api/v1/items/{item_id}`
- `POST /api/v1/items/upload-image`
- `POST /api/v1/items/sync`

### 14.5 发布

- `POST /api/v1/publish/item`

### 14.6 回复与发货

- `GET/PUT /api/v1/default-replies/{account_id}`
- `GET/PUT /api/v1/confirm-receipt/{account_id}`
- `GET/POST/DELETE /api/v1/keywords`
- `GET/PUT/DELETE /api/v1/delivery/configs/...`

### 14.7 订单与统计

- `POST /api/v1/orders/sync`
- `GET /api/v1/orders`
- `GET /api/v1/statistics/overview`
- `GET /api/v1/statistics/daily`

---

## 15. 开发说明

### 15.1 前端本地开发

```bash
cd frontend
npm install
npm run dev
```

### 15.2 后端本地开发

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 15.3 Playwright

如果本地不是 Docker 环境，首次运行可能需要安装浏览器：

```bash
playwright install chromium
```

---

## 16. 部署建议

推荐做法：

1. 使用 Docker Compose 部署
2. 前面加 Nginx 反向代理
3. 只暴露前端入口和必要 API
4. 备份 MySQL 数据卷
5. 定期检查登录状态

如果部署到公网：

- 不建议直接暴露数据库端口
- 建议修改默认管理员密码
- 建议修改数据库默认密码
- 建议用 HTTPS

---

## 17. 常见问题

### 17.1 网站能打开，但没有数据

先检查：

- 是否已登录后台
- 是否有账号接入
- 是否同步过商品
- 后端 API 是否正常

### 17.2 扫码登录后仍提示 Cookie 失效

常见原因：

- Cookie 没完整保存
- 页面跳转逻辑没同步
- 平台已让该 Cookie 失效

处理方式：

- 重新扫码登录
- 检查后端登录日志

### 17.3 商品同步失败

重点检查：

- 账号是否仍在线
- WebSocket 是否连接成功
- 平台接口是否返回权限错误

### 17.4 发布失败

排查顺序建议：

1. 看 `publish_error`
2. 看后端日志
3. 看发布页是否仍能手动打开
4. 看是否上传了图片
5. 看是否跳到了商品详情页

### 17.5 商品已经发出去了，但系统还显示失败

这类问题以前出现过，原因是：

- 页面已经跳转到商品详情页
- 但程序没有识别成功 URL

当前版本已经补了这类判定。

---

## 18. 已知问题与后续可优化点

当前版本能用，但不是终点。后续仍可继续优化：

- 发布成功后前端自动刷新状态
- 更细的发布日志展示
- 商品标题录入阶段前端直接做 30 字限制
- 更强的发布后校验
- 更稳的滑块 / 风控处理
- 更完整的商品分类、所在地、发货方式自动适配

---

## 19. 安全提醒

请特别注意：

- 不要把服务器 IP、密码、Cookie、Token 写进公开 README
- 不要把 GitHub Token 明文写进远端地址长期使用
- 如果远端地址里曾暴露 Token，建议立刻去 GitHub 撤销

---

## 20. License

当前仓库未单独附带开源许可证时，默认按你的私有项目使用和管理。

