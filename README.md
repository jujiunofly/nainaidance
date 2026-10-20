# 奶奶如厕记录

一个面向家庭照护场景的如厕记录工具。记录统一保存在服务器上，手机和电脑访问同一份数据；每次记录会通过 Telegram Bot 发送通知。

## 功能

- 今日「已如厕 / 未如厕」快速记录
- 自动显示距上次如厕约多少天
- 单屏显示完整月历，支持补记和修改历史日期
- 数据以服务器 JSON 文件为准，浏览器只保存只读缓存用于首屏加速
- 手机、电脑和其他设备共享同一份记录
- 页面先显示浏览器缓存，再从服务器刷新；每 15 秒自动同步，切回页面时立即刷新
- 每次记录通过服务端接口发送 Telegram 消息
- 支持带列宽的 Excel 导出、JSON 备份与恢复
- 右上角「数据」菜单可编辑记录和具体如厕时间
- Docker Compose 部署，数据通过项目目录下的 `./data` 持久化

## 快速开始

1. 复制环境变量模板：

   ```bash
   cp .env.example .env
   ```

   Windows PowerShell 可使用：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 编辑 `.env`，填入 Telegram Bot Token 和 Chat ID：

   ```dotenv
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

3. 启动：

   ```bash
   docker compose up -d --build
   ```

4. 打开 `http://localhost:8380`。

停止服务：

```bash
docker compose down
```

服务端数据保存在项目目录下的 `./data` 文件夹中，容器内路径为 `/data`。普通停止、重启或重建容器都不会丢失：

```text
/opt/nainaidance/data/records.json
```

注意：`docker compose down -v` 不会删除 `./data` 绑定目录，但手动删除 `data/` 会删除全部记录。`data/` 已加入 `.gitignore`，不会提交到 Git。

## 安全说明

Telegram Bot Token 只放在服务端环境变量中，不会进入 `public/index.html`。`.env` 已被 `.gitignore` 忽略，不要提交或公开真实 Token。

当前项目没有内置用户登录。若部署到公网，建议在反向代理层增加身份验证，或只部署在家庭内网/VPN 中。

## 项目结构

```text
.
├── public/
│   └── index.html
├── server.py
├── entrypoint.sh
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── data/              # 运行数据，已被 Git 忽略
└── README.md
```

## 接口

- `GET /api/health`：健康检查
- `GET /api/records`：读取全部记录
- `POST /api/records`：设置、删除、清空或导入记录
- `POST /api/notify`：转发消息到 Telegram

`POST /api/records` 示例：

```json
{
  "action": "set",
  "date": "2026-10-18",
  "record": {
    "status": "yes",
    "updatedAt": 1760790000000,
    "toiletAt": 1760790000000,
    "timeKnown": true
  }
}
```




