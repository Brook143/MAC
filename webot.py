import requests
import time
import json
import base64
import random
import qrcode
import os
import urllib.parse
import uuid
import string
import threading
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from agent import run_agent
from getall import fetch_and_cache

# ========== 日志配置 ==========
LOG_FILE = "webot.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== 配置区 ==========
BASE_URL = "https://ilinkai.weixin.qq.com"
WECHAT_VERSION = "8.0.72"
TOKEN_CACHE_FILE = "weixin_tokens.json"

# 新增：股票数据更新配置
STOCK_UPDATE_HOUR = 0
STOCK_UPDATE_MINUTE = 0
UPDATE_ON_STARTUP = True

# ========== 辅助函数 ==========
def generate_random_uin():
    random_uint32 = random.randint(0, 2**32 - 1)
    return base64.b64encode(str(random_uint32).encode()).decode()

def build_headers(token=None):
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": generate_random_uin(),
        "iLink-App-ClientVersion": WECHAT_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# ========== 多用户 Token 管理 ==========
def save_token(user_id, bot_token):
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {}
    data[user_id] = {
        "bot_token": bot_token,
        "login_time": datetime.now().isoformat()
    }
    with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.chmod(TOKEN_CACHE_FILE, 0o600)
    logger.info(f"Token 已保存到 {TOKEN_CACHE_FILE}，用户: {user_id}")

def load_token(user_id):
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(user_id, {}).get("bot_token")
    except:
        return None

def get_all_users():
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def remove_user(user_id):
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if user_id in data:
            del data[user_id]
            with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"用户 '{user_id}' 已从缓存中移除")
            return True
    except Exception as e:
        logger.error(f"移除用户 '{user_id}' 失败: {e}")
    return False

# ========== 认证模块 ==========
def get_qrcode():
    url = f"{BASE_URL}/ilink/bot/get_bot_qrcode?bot_type=3"
    logger.info(f"正在从 {url} 获取二维码...")
    try:
        resp = requests.get(url, headers={"iLink-App-ClientVersion": WECHAT_VERSION})
        resp.raise_for_status()
        data = resp.json()
        logger.debug(f"获取二维码接口返回: {data}")
    except requests.exceptions.RequestException as e:
        logger.error(f"获取二维码失败: {e}")
        return None

    qrcode_token = data.get("qrcode")
    qrcode_url = data.get("qrcode_img_content")

    if not qrcode_token or not qrcode_url:
        logger.error(f"返回数据不完整，缺少 qrcode 或 qrcode_img_content。完整返回: {data}")
        return None

    qr = qrcode.QRCode()
    qr.add_data(qrcode_url)
    qr.make()
    qr.print_ascii(invert=True)
    print("\n请用微信扫描上面的二维码")
    return qrcode_token

def wait_for_scan(qrcode_token, timeout=120):
    url = f"{BASE_URL}/ilink/bot/get_qrcode_status?qrcode={qrcode_token}"
    logger.info(f"开始轮询扫码状态: {url}")
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, headers={"iLink-App-ClientVersion": WECHAT_VERSION})
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "confirmed":
                logger.info("登录成功！")
                return data.get("bot_token")
            elif status == "scaned":
                logger.info("已扫码，请在手机上确认登录...")
            elif status == "expired":
                logger.warning("二维码已过期")
                break
            elif status == "wait":
                print(".", end="", flush=True)
            else:
                logger.warning(f"未知状态: {data}")
            time.sleep(3)
        except requests.exceptions.RequestException as e:
            logger.error(f"轮询出错: {e}")
            time.sleep(5)
    raise TimeoutError("等待扫码超时")

def login_new_user():
    """登录一个新用户，返回 (user_id, bot_token)"""
    token = get_qrcode()
    if not token:
        return None, None
    try:
        bot_token = wait_for_scan(token)
    except TimeoutError:
        logger.warning("扫码超时，登录取消")
        return None, None
    if not bot_token:
        return None, None

    user_id = input("请为这个账号设置标识名（如：小号1、工作号）: ").strip()
    if not user_id:
        user_id = f"user_{int(time.time())}"
    save_token(user_id, bot_token)
    logger.info(f"用户 '{user_id}' 登录成功，token 已保存")
    return user_id, bot_token

# ========== 消息收发模块 ==========
def get_updates(token, buf=""):
    url = f"{BASE_URL}/ilink/bot/getupdates"
    headers = build_headers(token)
    payload = {
        "get_updates_buf": buf,
        "base_info": {"channel_version": "1.0.2"}
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        msgs = data.get("msgs", [])
        new_buf = data.get("get_updates_buf", "")
        return msgs, new_buf
    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {e}")
        return [], buf

def generate_unique_client_id():
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"python_bot_{random_str}_{int(time.time() * 1000)}"

def send_message(token, to_user, text, context_token, from_user_id=""):
    url = f"{BASE_URL}/ilink/bot/sendmessage"
    headers = build_headers(token)
    payload = {
        "msg": {
            "from_user_id": from_user_id,
            "to_user_id": to_user,
            "client_id": generate_unique_client_id(),
            "message_type": 2,
            "message_state": 2,
            "item_list": [
                {"type": 1, "text_item": {"text": text}}
            ],
            "context_token": context_token,
        },
        "base_info": {"channel_version": "1.0.2"}
    }
    logger.info(f"正在向 {to_user} 发送消息: {text}")
    try:
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        logger.info("sendmessage 成功")
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"sendmessage 失败: {e}")
        return None

# ========== 股票数据定时更新 ==========
def stock_update_daemon():
    logger.info(f"定时更新服务已启动，每天 {STOCK_UPDATE_HOUR:02d}:{STOCK_UPDATE_MINUTE:02d} 更新数据")
    if UPDATE_ON_STARTUP:
        logger.info("程序启动，立即执行第一次数据更新...")
        try:
            fetch_and_cache()
            logger.info("启动时数据更新完成")
        except Exception as e:
            logger.error(f"启动时更新失败: {e}")
    while True:
        now = datetime.now()
        next_update = now.replace(hour=STOCK_UPDATE_HOUR, minute=STOCK_UPDATE_MINUTE, second=0, microsecond=0)
        if next_update <= now:
            next_update += timedelta(days=1)
        wait_seconds = (next_update - now).total_seconds()
        hours, remainder = divmod(wait_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        logger.info(f"下一次数据更新时间: {next_update.strftime('%Y-%m-%d %H:%M:%S')}，等待 {int(hours)}小时{int(minutes)}分{int(seconds)}秒")
        time.sleep(wait_seconds)
        logger.info("开始执行每日数据更新...")
        try:
            fetch_and_cache()
            logger.info("每日数据更新完成")
        except Exception as e:
            logger.error(f"每日数据更新失败: {e}")
            logger.info("10分钟后重试...")
            time.sleep(600)
            try:
                fetch_and_cache()
                logger.info("重试更新成功")
            except Exception as e2:
                logger.error(f"重试也失败了: {e2}")

# ========== 每个用户独立的消息监听线程 ==========
def user_message_loop(user_id, token, stop_event):
    """
    单个用户的消息监听循环
    stop_event: threading.Event，用于外部控制停止
    """
    buf = ""
    processed_msg_ids = set()
    logger.info(f"[{user_id}] 消息监听线程已启动")

    while not stop_event.is_set():
        try:
            msgs, new_buf = get_updates(token, buf)
            if new_buf:
                buf = new_buf

            for msg in msgs:
                if msg.get("message_type") != 1:
                    continue

                msg_id = msg.get("message_id")
                if msg_id in processed_msg_ids:
                    continue
                processed_msg_ids.add(msg_id)

                # 提取文本
                text = ""
                for item in msg.get("item_list", []):
                    if item.get("type") == 1:
                        text += item.get("text_item", {}).get("text", "")
                if not text:
                    continue

                from_user = msg.get("from_user_id", "")
                to_user = msg.get("to_user_id", "")
                context_token = msg.get("context_token", "")

                logger.info(f"[{user_id}] 收到来自 {from_user} 的消息: {text}")

                # 调用 agent（传入 from_user 作为 user_id，实现上下文隔离）
                reply = run_agent(from_user, text)
                logger.info(f"[{user_id}] Agent 回复: {reply}")

                send_message(token, from_user, reply, context_token, from_user_id=to_user)
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"[{user_id}] 消息循环异常: {e}")
            time.sleep(5)

    logger.info(f"[{user_id}] 消息监听线程已停止")

# ========== 启动入口 ==========
if __name__ == "__main__":
    logger.info("========== 多用户微信机器人启动 ==========")

    # 1. 启动股票数据定时更新线程（全局只需要一个）
    update_thread = threading.Thread(target=stock_update_daemon, daemon=True)
    update_thread.start()

    # 2. 加载所有已登录用户，启动监听线程
    users_data = get_all_users()
    active_threads = {}      # user_id -> {"thread": Thread, "stop_event": Event}

    for user_id, user_data in users_data.items():
        token = user_data.get("bot_token")
        if token:
            stop_event = threading.Event()
            t = threading.Thread(
                target=user_message_loop,
                args=(user_id, token, stop_event),
                daemon=True,
                name=f"listener-{user_id}"
            )
            t.start()
            active_threads[user_id] = {"thread": t, "stop_event": stop_event}
            logger.info(f"已启动用户 '{user_id}' 的消息监听")

    # 3. 交互式命令行菜单
    print("\n========== 多用户微信机器人 ==========")
    print("命令: [a]添加账号  [l]列出账号  [d]删除账号  [q]退出")
    print("提示: 直接按 Ctrl+C 也可以退出整个程序\n")

    try:
        while True:
            cmd = input("输入命令: ").strip().lower()

            if cmd == "a":
                user_id, token = login_new_user()
                if user_id and token:
                    stop_event = threading.Event()
                    t = threading.Thread(
                        target=user_message_loop,
                        args=(user_id, token, stop_event),
                        daemon=True,
                        name=f"listener-{user_id}"
                    )
                    t.start()
                    active_threads[user_id] = {"thread": t, "stop_event": stop_event}
                    logger.info(f"用户 '{user_id}' 已上线")

            elif cmd == "l":
                print("\n当前账号状态:")
                if not active_threads:
                    print("  （无）")
                for uid, info in active_threads.items():
                    alive = "运行中" if info["thread"].is_alive() else "已停止"
                    print(f"  - {uid}: {alive}")
                print()

            elif cmd == "d":
                uid = input("要删除的账号标识名: ").strip()
                if uid in active_threads:
                    logger.info(f"正在停止 '{uid}' 的监听线程...")
                    active_threads[uid]["stop_event"].set()
                    active_threads[uid]["thread"].join(timeout=5)
                    del active_threads[uid]
                    remove_user(uid)
                    logger.info(f"用户 '{uid}' 已删除")
                else:
                    logger.warning(f"未找到用户 '{uid}'")

            elif cmd == "q":
                logger.info("正在停止所有监听线程...")
                for uid, info in active_threads.items():
                    info["stop_event"].set()
                for uid, info in active_threads.items():
                    info["thread"].join(timeout=5)
                logger.info("程序退出")
                break

            else:
                print("未知命令，可用: a(添加) l(列表) d(删除) q(退出)")

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止所有线程...")
        for uid, info in active_threads.items():
            info["stop_event"].set()
        for uid, info in active_threads.items():
            info["thread"].join(timeout=5)
        logger.info("程序已退出")
