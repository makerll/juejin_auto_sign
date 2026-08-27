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
from email.mime.multipart import MIMEMultipart
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


def send_mail(cfg, subject, text, html=None):
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
    if html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(text, "plain", "utf-8")
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


def build_html(r):
    """清新简约的邮件 HTML 模板（内联样式，兼容主流邮件客户端）。"""
    signed_str = r.get("signed", "—")

    def row(label, value, color="#1f4438"):
        return (
            '<tr>'
            f'<td style="padding:11px 0;font-size:14px;color:#8aa098;">{label}</td>'
            f'<td style="padding:11px 0;font-size:14px;font-weight:600;color:{color};text-align:right;">{value}</td>'
            '</tr>'
        )

    rows_html = (
        row("签到状态", signed_str, "#34b98b" if signed_str.startswith("已") else "#e09d3f")
        + row("免费抽奖", r.get("draw", "—"))
        + row("当前矿石", r.get("point", "—"))
        + row("连续签到", r.get("cont", "—"))
        + row("累计签到", r.get("sum", "—"))
    )
    return (
        '<div style="background-color:#eef2f1;padding:32px 16px;'
        'font-family:-apple-system,\'Segoe UI\',\'Microsoft YaHei\',\'PingFang SC\',sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:520px;margin:0 auto;">'
        '<tr><td style="background:#ffffff;border-radius:16px;padding:28px 32px;">'
        '<p style="margin:0 0 4px;font-size:12px;letter-spacing:3px;color:#a9c0b8;">JUEJIN · CHECK-IN</p>'
        '<h1 style="margin:0 0 18px;font-size:20px;font-weight:600;color:#1f4438;">掘金每日打卡</h1>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-top:1px solid #f0f3f2;">' + rows_html + '</table>'
        '<p style="margin:20px 0 0;font-size:12px;color:#b4c0bc;background:#f6f9f8;'
        'border-radius:8px;padding:10px 14px;">' + str(r.get("date", "")) + '</p>'
        '</td></tr></table></div>'
    )


def main():
    cfg = load_config()
    cookie = os.environ.get("JUEJIN_COOKIE") or cfg.get("cookie", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"掘金自动任务执行时间: {now}", ""]
    report = {"date": now, "signed": "未知", "draw": "—", "point": "—", "cont": "—", "sum": "—"}

    # 1. 检查签到状态
    st = api_get(f"{BASE}/get_today_status", cookie)
    if st.get("err_no") != 0:
        lines.append(f"[ERROR] 查询签到状态失败: {st.get('err_msg')}（Cookie 可能失效）")
        print("\n".join(lines))
        return 2
    signed = bool(st.get("data", False))
    report["signed"] = "已签到" if signed else "未签到"
    lines.append(f"签到状态: {report['signed']}")

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
            report["draw"] = f"{d.get('lottery_name', '未知奖品')} · 矿{d.get('total_point', '?')}"
            lines.append(f"抽奖结果: {report['draw']}")
    else:
        lines.append("今日免费抽奖次数已用完，跳过")

    # 4. 剩余矿石
    pt = api_get(f"{BASE}/get_cur_point", cookie)
    if pt.get("err_no") == 0 and pt.get("data"):
        report["point"] = f"{pt['data']} 矿石"
        lines.append(f"当前矿石: {pt['data']}")

    # 5. 签到天数汇总
    ct = api_get(f"{BASE}/get_counts", cookie)
    if ct.get("err_no") == 0 and ct.get("data"):
        report["cont"] = f"{ct['data'].get('cont_count', '?')} 天"
        report["sum"] = f"{ct['data'].get('sum_count', '?')} 天"
        lines.append(f"连续签到: {report['cont']}")
        lines.append(f"累计签到: {report['sum']}")

    content = "\n".join(lines)
    print(content)

    # 6. 发送邮件
    html = build_html(report)
    mail_res = send_mail(cfg, f"掘金每日打卡 {now[:10]}", content, html)
    print(mail_res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
