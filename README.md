# MAC 股票助手

基于微信机器人的智能股票分析多智能体系统，支持自然语言对话查询个股行情、筛选特殊股票，内置多轮对话记忆与风险提示。

---

## 功能特性

- **多账号管理**：支持同时登录多个微信账号，每个账号独立线程监听消息
- **智能路由**：基于 LLM 的意图识别，准确判断用户是想查个股、筛选股票还是闲聊
- **多轮对话**：维护会话历史，支持"继续""那它呢"等指代词消歧
- **个股分析**：调用 Tushare 获取近十日行情，结合 LLM 做客观分析
- **股票筛选**：基于 Redis 缓存数据，按连涨天数、涨跌幅、特殊数字规则筛选值得关注的股票
- **风险提示**：非聊天类回复自动追加风险提示，合规友好

---

## 项目架构

```
MAC/
├── webot.py              # 主程序：微信 iLink Bot 协议、多账号线程、定时任务
├── agent.py              # 编排入口：路由分发、会话历史管理、风险提示
├── agents/
│   ├── router.py        # 意图路由智能体（快速路径 + LLM 路由 + 规则兜底）
│   ├── chat_agent.py    # 闲聊智能体
│   ├── scanner_agent.py  # 股票筛选智能体（调用 find_special_stocks 工具）
│   ├── stock_agent.py   # 个股分析智能体（调用 fetch_stock_data 工具）
│   ├── llm.py          # LLM 工厂：根据 agent 名构造 ChatOpenAI 实例
│   └── tool_runner.py  # 通用工具调用循环（最多 5 轮）
├── tools/
│   ├── find_data.py     # 特殊股票筛选工具（连涨>2 且涨幅 2~7% 且最低价小数部分两位相同）
│   └── fetch_data.py   # 个股行情拉取工具（Tushare pro.daily）
├── getall.py            # 定时任务：分页拉取全市场日线，筛选主板，计算连涨天数，批量写 Redis
├── rediscache.py       # Redis 客户端封装（带降级模式）
├── requirements.txt     # Python 依赖
├── .env.example        # 环境变量示例
└── .gitignore         # Git 忽略规则
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或使用项目自带虚拟环境：

```bash
.\env\Scripts\activate
```

### 2. 启动 Redis

**Windows 本地安装方式**：

下载 Redis for Windows 移植版：https://github.com/tporadowski/redis/releases

解压后编辑 `redis.windows.conf`，设置密码：
```
requirepass xuyuze
```

启动 Redis：
```bash
redis-server.exe redis.windows.conf
```

验证：
```bash
redis-cli.exe -a xuyuze ping
# 返回 PONG 即成功
```

### 3. 配置并启动程序

复制 `.env.example` 为 `.env`，填写必要配置后启动：

```bash
python webot.py
```

---

## 使用说明

### 登录账号

启动后输入命令 `a` → 终端显示二维码 → **微信扫码** → 手机确认 → 输入标识名（如 `小号1`）

重复以上步骤可登录多个账号。

### 常用命令

| 命令 | 作用 |
|------|------|
| `a` | 添加账号（扫码登录） |
| `l` | 列出所有在线账号 |
| `d` | 删除账号（停止监听并移除） |
| `q` | 退出程序 |

### 对话示例

```
用户：000001.SZ 怎么样
助手：近十日收盘价...（个股分析）

用户：那它呢
助手：近十日收盘价...（结合上下文，继续分析 000001.SZ）

用户：最近有什么特殊股票
助手：筛选结果...（调用 find_special_stocks 工具）

用户：继续
助手：...（结合筛选结果继续推荐）
```

---

## 注意事项

1. **Token 过期**：输入 `d` 删除旧账号，重新 `a` 扫码登录
2. **多账号建议**：3 个以内，每个账号一个线程
3. **敏感文件**：`.env`、`weixin_tokens.json` 已加入 `.gitignore`，请勿上传到公开仓库
4. **Redis 必需**：项目依赖 Redis 缓存股票数据，未安装 Redis 会降级但功能受限
5. **Tushare Token**：需自行申请 Tushare Token（https://tushare.pro/register）
