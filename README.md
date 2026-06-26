# 多用户微信机器人

支持多账号同时在线，每个账号独立线程监听消息。

---

## 快速开始

### 1. 启动程序

```bash
python webot.py
```

### 2. 登录账号

输入命令 `a` → 终端显示二维码 → **微信扫码** → 手机确认 → 输入标识名（如 `小号1`）

重复以上步骤可登录多个账号。

### 3. 常用命令

| 命令 | 作用 |
|------|------|
| `a` | 添加账号（扫码登录） |
| `l` | 列出所有在线账号 |
| `d` | 删除账号（停止监听并移除） |
| `q` | 退出程序 |

### 4. 查看日志

```bash
tail -f webot.log
```

---

## Docker 部署

### 构建镜像

```bash
docker build -t webot .
```

### 运行容器

```bash
docker run -d \
  --name webot \
  -v $(pwd)/weixin_tokens.json:/app/weixin_tokens.json \
  -v $(pwd)/webot.log:/app/webot.log \
  webot
```

### 进入容器交互（扫码登录用）

```bash
docker exec -it webot python webot.py
```

输入 `a` 扫码登录，登录成功后按 `q` 退出交互，后台线程继续运行。

### 查看日志

```bash
docker logs -f webot
```

### 停止/重启

```bash
docker stop webot
docker start webot
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `webot.py` | 主程序 |
| `weixin_tokens.json` | 账号 token 缓存（登录后自动生成） |
| `webot.log` | 运行日志 |

---

## 注意事项

1. **首次登录**：必须在交互模式下扫码（`docker exec -it`），登录成功后 token 会保存到 `weixin_tokens.json`
2. **token 过期**：输入 `d` 删除旧账号，重新 `a` 扫码登录
3. **多账号建议**：3 个以内，每个账号一个线程
4. **敏感文件**：`weixin_tokens.json` 不要上传到公开仓库
