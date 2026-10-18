# 奶奶如厕记录

一个面向家庭照护场景的单页如厕记录工具。页面会记录每天是否如厕、显示距上次如厕的整天数，并在每次记录后通过 Telegram Bot 发送通知。

## 功能

- 今日「已如厕 / 未如厕」快速记录
- 自动显示距上次如厕约多少天
- 单屏显示完整月历，支持补记和修改历史日期
- 记录保存在浏览器 `localStorage`，不会上传到第三方
- 每次记录通过服务端接口发送 Telegram 消息
- 支持 CSV 导出、JSON 备份与恢复
- Docker Compose 一键部署

## 快速开始

1. 复制环境变量模板：

   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env`，填入 Telegram Bot Token 和 Chat ID：

   ```dotenv
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   APP_PORT=8080
   ```

3. 启动：

   ```bash
   docker compose up -d --build
   ```

4. 打开 `http://localhost:8080`。

停止服务：

```bash
docker compose down
```

## 安全说明

Telegram Bot Token 只放在服务端环境变量中，不会进入 `public/index.html`。`.env` 已被 `.gitignore` 忽略，不要提交或公开真实 Token。

如果使用 GitHub Pages 或其他纯静态托管，页面本身无法安全保存 Bot Token，也无法发送 Telegram 消息；需要把本项目的 `server.py` 与静态页面一起部署，或者使用自己的后端代理。

## 项目结构

```text
.
├── public/
│   └── index.html
├── server.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 接口

- `GET /api/health`：健康检查
- `POST /api/notify`：接收 `{"message":"..."}` 并转发到 Telegram
