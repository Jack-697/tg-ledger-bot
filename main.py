import os
import requests
import telebot
from decimal import Decimal, ROUND_HALF_UP

# 优先从环境变量读取 BOT_TOKEN，若未配置则使用默认 Token 兜底
TOKEN = os.getenv("BOT_TOKEN", "9146607239:AAGh5cnKEPmfZvnBBBJxXYb-2-HKAtkhdwg")
bot = telebot.TeleBot(TOKEN)

# ================= 🛡️ 核心：白名单管理员 Telegram 数字 ID =================
ALLOWED_USER_IDS = [
    6419326729,  # 你的专属 Telegram 数字 ID
]

# 内存数据存储结构
group_data = {}

def get_group(chat_id):
    if chat_id not in group_data:
        group_data[chat_id] = {
            "is_running": True,          # 默认上课状态
            "rate": Decimal("9"),        # 默认账单汇率
            "deposits": [],              # 入款列表
            "payouts": [],               # 下发列表
            "operators": set()           # 操作人集合（存用户名小写）
        }
    return group_data[chat_id]

def format_money(val):
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# 获取真实 USDT 实时汇率接口 (OKX / Huobi)
def get_realtime_usdt_rate():
    try:
        url = "https://www.okx.com/api/v5/market/index-tickers?instId=USDT-CNY"
        response = requests.get(url, timeout=3)
        data = response.json()
        if data.get("code") == "0" and data.get("data"):
            return float(data["data"][0]["idxPx"])
    except Exception:
        pass
    try:
        url = "https://api.huobi.pro/market/detail/merged?symbol=usdtcny"
        response = requests.get(url, timeout=3)
        data = response.json()
        if data.get("status") == "ok" and "tick" in data:
            return float(data["tick"]["close"])
    except Exception:
        pass
    return 6.68

# ================= 1. 基础控制（仅限白名单管理员） =================
@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["开始", "上课"])
def cmd_start(message):
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        return
    g = get_group(message.chat.id)
    g["is_running"] = True
    bot.reply_to(message, "【系统提示】已开启（上课），当前群组开始正常记账。")

@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["停止", "下课"])
def cmd_stop(message):
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        return
    g = get_group(message.chat.id)
    g["is_running"] = False
    bot.reply_to(message, "【系统提示】已暂停（下课），当前群组已停止记账。")

# ================= 2. 角色管理（仅限白名单管理员） =================
@bot.message_handler(func=lambda m: m.text and (m.text.startswith("设置操作人") or m.text.startswith("删除操作人") or m.text.strip() == "显示操作人"))
def cmd_roles(message):
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        return
    g = get_group(message.chat.id)
    text = message.text.strip()
    
    if text.startswith("设置操作人"):
        parts = message.text.replace("设置操作人", "").strip()
        if parts.startswith("@"):
            target_name = parts[1:].strip().lower()
            g["operators"].add(target_name)
            op_list_str = ", ".join([f"@{name}" for name in g["operators"]])
            bot.reply_to(message, f"【角色管理】设置成功！当前授权操作人列表：\n{op_list_str}")
        else:
            bot.reply_to(message, "【格式错误】请使用格式：设置操作人 @用户名")
            
    elif text.startswith("删除操作人"):
        parts = message.text.replace("删除操作人", "").strip()
        if parts.startswith("@"):
            target_name = parts[1:].strip().lower()
            if target_name in g["operators"]:
                g["operators"].remove(target_name)
                op_list_str = ", ".join([f"@{name}" for name in g["operators"]]) if g["operators"] else "（暂无）"
                bot.reply_to(message, f"【角色管理】已成功移除 @{target_name}。当前操作人列表：\n{op_list_str}")
            else:
                bot.reply_to(message, f"【格式错误】操作人 @{target_name} 不存在")
        else:
            bot.reply_to(message, "【格式错误】请使用格式：删除操作人 @用户名")
            
    elif text == "显示操作人":
        ops = g["operators"]
        if not ops:
            bot.reply_to(message, "【角色管理】当前操作人列表为空。")
        else:
            op_list_str = ", ".join([f"@{name}" for name in ops])
            bot.reply_to(message, f"【角色管理】当前授权操作人列表：\n{op_list_str}")

# ================= 3. 配置命令（设置汇率，仅限白名单管理员） =================
@bot.message_handler(func=lambda m: m.text and m.text.startswith("设置汇率"))
def set_rate(message):
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        return
    try:
        val_str = message.text.replace("设置汇率", "").strip()
        rate = Decimal(val_str)
        g = get_group(message.chat.id)
        g["rate"] = rate
        bot.reply_to(message, f"【配置成功】账单计算汇率已更新为: {rate}")
    except Exception:
        bot.reply_to(message, "【格式错误】请发送：设置汇率9 （或 设置汇率7.5）")

# ================= 4. 账单与工具命令（仅限白名单管理员） =================
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "z0")
def cmd_z0(message):
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        return
    real_rate = get_realtime_usdt_rate()
    bot.reply_to(message, f"【USDT实时汇率】OKX/HTX市场参考价: {real_rate:.2f} (行情实时平稳)")

@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["清空账单", "删除账单", "删除历史账单"])
def clear_bills(message):
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        return
    g = get_group(message.chat.id)
    g["deposits"] = []
    g["payouts"] = []
    bot.reply_to(message, "【账单重置】今日账单及历史账单已全部清空。")

@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["查账", "显示账单", "+0", "显示完整账单"])
def show_bills(message):
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        return
    send_report(message.chat.id)

# ================= 5. 核心消息与计算逻辑 =================
@bot.message_handler(func=lambda m: True)
def handle_ledger(message):
    if not message.text:
        return

    text = message.text.strip().replace(" ", "")
    chat_id = message.chat.id
    g = get_group(chat_id)
    
    if not g.get("is_running", True):
        return
        
    rate = g["rate"]
    import time
    local_time = time.strftime("%H:%M:%S", time.localtime(time.time()))

    try:
        # 【规则 1】：群里所有人发送加减乘除算式（包含 * 或 /），都正常返回计算结果
        if ("*" in text or "/" in text) and not text.startswith("+") and not text.startswith("-") and not text.startswith("下发"):
            allowed_chars = set("0123456789.*/()")
            if all(c in allowed_chars for c in text):
                result = eval(text)
                if isinstance(result, float):
                    result = format_money(Decimal(str(result)))
                bot.reply_to(message, f"🧮 计算结果: {text} = {result}")
                return

        # 检查是否为记账指令（下发 或 + / -）
        is_ledger_cmd = False
        if text.startswith("下发") or text.startswith("+") or text.startswith("-"):
            is_ledger_cmd = True

        if is_ledger_cmd:
            # 【规则 2：记账权限校验】只有 管理员 ID 或 被“设置操作人”添加进名单的人 可以记账
            is_authorized = False
            if ALLOWED_USER_IDS and message.from_user.id in ALLOWED_USER_IDS:
                is_authorized = True
            else:
                sender_username = message.from_user.username
                if sender_username and sender_username.lower() in g["operators"]:
                    is_authorized = True

            if not is_authorized:
                return  # 没权限的人发记账指令直接忽略

            # A. 下发命令
            if text.startswith("下发"):
                cny_str = text.replace("下发", "")
                cny = Decimal(cny_str)
                u = format_money(cny / rate)
                g["payouts"].append({"cny": cny, "u": u, "time": local_time})
                send_report(chat_id)
                return

            # B. 入款命令 (+ / -)
            if text.startswith("+") or text.startswith("-"):
                is_negative = text.startswith("-")
                clean_text = text[1:]
                custom_rate = rate
                if "/" in clean_text:
                    parts = clean_text.split("/")
                    clean_text = parts[0]
                    custom_rate = Decimal(parts[1])
                cny = Decimal(clean_text)
                if is_negative:
                    cny = -cny
                u = format_money(cny / custom_rate)
                g["deposits"].append({"cny": cny, "u": u, "time": local_time})
                send_report(chat_id)
                return

    except Exception:
        pass

def send_report(chat_id):
    g = get_group(chat_id)
    rate = g["rate"]
    deps = g["deposits"]
    pays = g["payouts"]
    total_cny = sum([d["cny"] for d in deps], Decimal("0"))
    total_u = sum([d["u"] for d in deps], Decimal("0"))
    payout_u = sum([p["u"] for p in pays], Decimal("0"))
    balance_u = total_u - payout_u

    lines = ["MGM欢迎您来单！"]
    lines.append(f"今日入款 ({len(deps)}笔) :")
    if not deps:
        lines.append("（暂无）")
    else:
        for idx, d in enumerate(deps, 1):
            lines.append(f"【{idx}】 {d['time']} {int(d['cny'])} / {rate} = {d['u']} U")
    lines.append("")
    lines.append(f"今日下发 ({len(pays)}笔) :")
    if not pays:
        lines.append("（暂无）")
    else:
        for idx, p in enumerate(pays, 1):
            lines.append(f"【{idx}】 {p['time']} {int(p['cny'])} / {rate} = {p['u']} U")
    lines.append("")
    lines.append(f"总入款: {int(total_cny)}")
    lines.append(f"汇率: {rate}")
    lines.append("")
    lines.append(f"应下发: {total_u} U")
    lines.append(f"已下发: {payout_u} U")
    lines.append(f"未下发: {balance_u} U")
    bot.send_message(chat_id, "\n".join(lines))

if __name__ == "__main__":
    print("MGM欢迎您来单！全功能版机器人已启动，正在监听 Telegram 消息...")
    bot.infinity_polling()
