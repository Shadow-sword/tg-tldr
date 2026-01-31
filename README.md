# tg-tldr

Telegram 群聊记录器 + AI 每日总结工具。

使用 Telethon 以用户身份监听指定群聊消息，存储到 SQLite，每日定时调用 Claude API 生成群聊摘要并发送到指定群。

## 功能特性

- 📝 **消息记录** — 实时监听并存储指定群聊的所有文本消息
- 🧵 **回复关联** — 保留消息回复关系，支持嵌套线程
- 🤖 **AI 总结** — 使用 Claude 按话题线程生成每日摘要
- ⏰ **定时任务** — 内置调度器，每日自动生成并推送总结
- 🎯 **灵活过滤** — 支持按用户、关键词过滤消息（含通配符）
- 📤 **灵活投递** — 不同群的总结可发送到同一个或不同的目标群
- 🐳 **Docker 支持** — 提供 Dockerfile 和 docker-compose 配置

## 安装

### 前置条件

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器
- Telegram API 凭证（从 [my.telegram.org](https://my.telegram.org/apps) 获取）
- Anthropic API Key（从 [console.anthropic.com](https://console.anthropic.com/) 获取）

### 本地安装

```bash
# 克隆项目
git clone https://github.com/yourname/tg-tldr.git
cd tg-tldr

# 安装依赖
make install
# 或: uv sync

# 复制配置模板
cp .env.example .env
cp config.example.yaml config.yaml

# 编辑配置文件
vim .env          # 填入 API 凭证
vim config.yaml   # 配置监控的群聊
```

## 配置

### 环境变量 (.env)

```bash
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
ANTHROPIC_API_KEY=your_anthropic_api_key
# 可选：自定义 API 地址（代理或兼容端点）
ANTHROPIC_BASE_URL=
```

### 配置文件 (config.yaml)

```yaml
telegram:
  session_name: tg-tldr

groups:
  - name: "技术群"
    id: -1001234567890        # 群聊 ID
    summary_to: -1009999999999  # 总结发送目标
    filters:
      ignore_users: [123456789]           # 屏蔽用户
      ignore_keywords: ["*广告*", "*推广*"]  # 屏蔽关键词（支持 * 通配符）
  - name: "闲聊群"
    id: -1009876543210
    summary_to: -1009876543210  # 总结发回本群

summary:
  schedule: "09:00"              # 每日总结时间
  timezone: "Asia/Shanghai"
  default_send_to: -1009999999999
  model: "claude-sonnet-4-20250514"
```

### 过滤规则

| 配置项 | 说明 |
|---|---|
| `ignore_users` | 忽略这些用户的消息 |
| `only_users` | 只记录这些用户的消息 |
| `ignore_keywords` | 忽略包含关键词的消息 |
| `only_keywords` | 只记录包含关键词的消息 |

关键词支持 `*` 通配符：`*广告*` 匹配包含"广告"的消息，`广告*` 匹配以"广告"开头的消息。

## 使用

### 本地运行

```bash
# 启动守护进程（监听消息 + 定时总结）
make run

# 手动生成昨日总结
make summary

# 生成指定日期总结
make summary-date DATE=2026-01-30

# 清理早于指定日期的消息
make purge BEFORE=2026-01-01

# 打开数据库
make db-shell
```

首次运行会提示输入手机号进行 Telegram 登录验证。

### Docker 部署

```bash
# 构建镜像
make docker-build

# 首次运行（交互式登录）
make docker-run

# 登录成功后，后台运行
make docker-up

# 查看日志
make docker-logs

# 停止
make docker-down
```

## 可用命令

```bash
make help          # 显示帮助
make install       # 安装依赖
make run           # 启动守护进程
make summary       # 生成昨日总结
make summary-date  # 生成指定日期总结
make purge         # 清理旧消息
make lint          # 代码检查
make format        # 代码格式化
make clean         # 清理缓存
make db-shell      # 打开数据库
make docker-build  # 构建 Docker 镜像
make docker-run    # 首次交互式运行
make docker-up     # 后台启动
make docker-down   # 停止容器
make docker-logs   # 查看日志
make typecheck     # 类型检查
make ci            # 运行完整 CI 检查
```

## 数据存储

- `data/messages.db` — SQLite 数据库
  - `messages` 表：群聊消息记录
  - `summaries` 表：每日总结历史
- `data/tg-tldr.session` — Telegram 登录凭证

## License

MIT
