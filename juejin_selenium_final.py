# -*- coding: utf-8 -*-
"""掘金每日签到 + 免费抽奖脚本（使用 Cookie 免登录）。
读取同目录 config.json 中的 cookie 与发件配置，执行签到/抽奖，并可选发送结果邮件。
"""
import json
import os
import sys
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

BASE = "https://api.juejin.cn/growth_api/v1"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def load_config():
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def api_post(url, cookie, body=None):
    data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    req.add_header("Referer", "https://juejin.cn/")
    req.add_header("Origin", "https://juejin.cn")
    req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"err_msg": f"HTTP {e.code}", "raw": e.read().decode("utf-8", "ignore")}
    except Exception as e:
        return {"err_msg": str(e)}


def api_get(url, cookie):
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", UA)
    req.add_header("Referer", "https://juejin.cn/")
    req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"err_msg": f"HTTP {e.code}", "raw": e.read().decode("utf-8", "ignore")}
    except Exception as e:
        return {"err_msg": str(e)}


def send_mail(cfg, subject, content):
    smtp = cfg.get("smtp") or {}
    host = smtp.get("host") or os.environ.get("SMTP_SERVER", "smtp.163.com")
    port = int(smtp.get("port") or int(os.environ.get("SMTP_PORT", "465")))
    user = smtp.get("user") or os.environ.get("SMTP_USER", "")
    code = smtp.get("auth_code") or os.environ.get("SMTP_AUTH_CODE", "")
    to = os.environ.get("MAIL_TO") or cfg.get("receiver", "")
    if not (host and user and code):
        return "未配置发件SMTP（缺少SMTP授权码），跳过邮件发送"
    if not to:
        return "未配置收件邮箱（MAIL_TO），跳过邮件发送"
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(user, code)
        server.sendmail(user, [to], msg.as_string())
        server.quit()
        return "邮件发送成功"
    except Exception as e:
        return f"邮件发送失败: {e}"


def main():
    cfg = load_config()
    cookie = os.environ.get("JUEJIN_COOKIE") or cfg.get("cookie", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"掘金自动任务执行时间: {now}", ""]

    # 1. 检查签到状态
    st = api_get(f"{BASE}/get_today_status", cookie)
    if st.get("err_no") != 0:
        lines.append(f"[ERROR] 查询签到状态失败: {st.get('err_msg')}（Cookie 可能失效）")
        print("\n".join(lines))
        return 2
    signed = bool(st.get("data", False))
    lines.append(f"签到状态: {'今日已签到' if signed else '今日未签到'}")

    # 2. 执行签到
    if not signed:
        ck = api_post(f"{BASE}/check_in", cookie, {})
        if ck.get("err_no") != 0:
            lines.append(f"签到失败: {ck.get('err_msg')}")
        else:
            inc = (ck.get("data") or {}).get("incr_point")
            lines.append(f"签到成功 +{inc} 矿石")
    else:
        lines.append("无需重复签到")

    # 3. 免费抽奖一次
    lc = api_get(f"{BASE}/lottery_config/get", cookie)
    free_cnt = 0
    if lc.get("err_no") == 0 and lc.get("data"):
        free_cnt = lc["data"].get("free_count", 0)
    lines.append(f"今日免费抽奖次数: {free_cnt}")
    if free_cnt > 0:
        dr = api_post(f"{BASE}/lottery/draw", cookie, {})
        if dr.get("err_no") != 0:
            lines.append(f"抽奖失败: {dr.get('err_msg')}")
        else:
            d = dr.get("data") or {}
            lines.append(f"抽奖结果: {d.get('lottery_name', '未知奖品')} (矿{d.get('total_point', '?')} )")
    else:
        lines.append("今日免费抽奖次数已用完，跳过")

    # 4. 剩余矿石
    pt = api_get(f"{BASE}/get_cur_point", cookie)
    if pt.get("err_no") == 0 and pt.get("data"):
        lines.append(f"当前矿石: {pt['data']}")

    content = "\n".join(lines)
    print(content)

    # 5. 发送邮件
    mail_res = send_mail(cfg, f"掘金每日签到抽奖 {now[:10]}", content)
    print(mail_res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
