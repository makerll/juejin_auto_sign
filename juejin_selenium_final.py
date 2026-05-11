#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掘金社区自动签到脚本 - API稳定版
"""
import os
import time
import random
import requests
import smtplib
import ssl
import re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==================== 配置 ====================
COOKIE = os.environ.get('JUEJIN_COOKIE', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_TO = os.environ.get('EMAIL_TO', '')
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.163.com')

try:
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))
except:
    SMTP_PORT = 465

if not EMAIL_TO:
    EMAIL_TO = EMAIL_FROM

# API配置
BASE_URL = "https://api.juejin.cn"
CHECK_IN_URL = f"{BASE_URL}/growth_api/v1/check_in"
GET_STATUS_URL = f"{BASE_URL}/growth_api/v1/get_today_status"
LOTTERY_URL = f"{BASE_URL}/growth_api/v1/lottery/draw"
GET_CURRENT_POINT_URL = f"{BASE_URL}/growth_api/v1/get_cur_point"

# 随机User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

def get_china_time():
    """获取中国时间"""
    china_tz = timezone(timedelta(hours=8))
    return datetime.now(china_tz)

def format_china_time():
    """格式化中国时间"""
    return get_china_time().strftime('%Y-%m-%d %H:%M:%S')

def get_headers():
    """获取请求头"""
    return {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Type': 'application/json',
        'Origin': 'https://juejin.cn',
        'Referer': 'https://juejin.cn/',
        'User-Agent': random.choice(USER_AGENTS),
        'Cookie': COOKIE,
    }

def make_request(url, method='GET', data=None):
    """发送API请求"""
    headers = get_headers()
    
    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=10)
        else:
            resp = requests.post(url, headers=headers, json=data or {}, timeout=10)
        
        if resp.status_code == 200 and resp.text:
            return resp.json()
        return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def get_current_points():
    """获取当前矿石数"""
    result = make_request(GET_CURRENT_POINT_URL, 'GET')
    if result and result.get('err_no') == 0:
        return result.get('data', 0)
    return 0

def check_today_status():
    """检查今天是否已签到"""
    result = make_request(GET_STATUS_URL, 'GET')
    if result and result.get('err_no') == 0:
        return result.get('data', False)
    return False

def check_in():
    """执行签到"""
    result = make_request(CHECK_IN_URL, 'POST', {})
    if result and result.get('err_no') == 0:
        incr_point = result.get('data', {}).get('incr_point', 0)
        total_point = result.get('data', {}).get('total_point', 0)
        print(f"✅ 签到成功！获得 {incr_point} 矿石，当前总矿石: {total_point}")
        return True, incr_point
    else:
        error_msg = result.get('err_msg', '未知错误') if result else '请求失败'
        print(f"❌ 签到失败: {error_msg}")
        return False, 0

def lottery_draw():
    """执行抽奖"""
    result = make_request(LOTTERY_URL, 'POST', {})
    if result and result.get('err_no') == 0:
        lottery_name = result.get('data', {}).get('lottery_name', '未知')
        # 提取数字
        ore_match = re.search(r'(\d+)', lottery_name)
        if ore_match:
            ore = int(ore_match.group(1))
            print(f"🎉 抽奖获得: {lottery_name} ({ore}矿石)")
            return lottery_name, ore
        print(f"🎉 抽奖获得: {lottery_name}")
        return lottery_name, 0
    else:
        if result and result.get('err_msg'):
            if '今天已经抽过奖' in result.get('err_msg'):
                print("⏰ 今天已经抽过奖了")
                return "今天已经抽过奖", 0
        print("❌ 抽奖失败")
        return "抽奖失败", 0

def send_email(subject, content, is_html=False):
    """发送邮件通知"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject

        if is_html:
            msg.attach(MIMEText(content, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(content, 'plain', 'utf-8'))

        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=30)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        server.quit()
        print("✅ 邮件发送成功")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False

def create_email_html(sign_status, sign_ore, lottery_result, lottery_ore, total_ore, after_points):
    """创建HTML邮件内容"""
    current_time = format_china_time()
    
    today_ore = sign_ore + lottery_ore
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background: #f5f7fa;
                padding: 20px;
            }}
            .card {{
                max-width: 400px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 24px;
                box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                padding: 20px;
                background: linear-gradient(135deg, #1E80FF, #0052CC);
                color: white;
                text-align: center;
            }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 5px 0 0; opacity: 0.9; font-size: 12px; }}
            .content {{ padding: 20px; }}
            .stat-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-bottom: 20px;
            }}
            .stat-card {{
                background: #f8fafc;
                border-radius: 16px;
                padding: 16px;
                text-align: center;
            }}
            .stat-label {{ font-size: 12px; color: #64748b; margin-bottom: 4px; }}
            .stat-value {{ font-size: 24px; font-weight: 600; color: #0f172a; }}
            .result-card {{
                background: #f8fafc;
                border-radius: 16px;
                padding: 16px;
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .result-icon {{
                width: 48px;
                height: 48px;
                border-radius: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
            }}
            .sign-icon {{ background: #10b98120; }}
            .lottery-icon {{ background: #8b5cf620; }}
            .result-info {{ flex: 1; }}
            .result-title {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
            .sign-title {{ color: #10b981; }}
            .lottery-title {{ color: #8b5cf6; }}
            .result-desc {{ font-size: 12px; color: #64748b; }}
            .footer {{
                padding: 16px;
                text-align: center;
                border-top: 1px solid #f0f2f5;
                color: #94a3b8;
                font-size: 11px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h1>⛏️ 掘金签到</h1>
                <p>{current_time}</p>
            </div>
            <div class="content">
                <div class="stat-grid">
                    <div class="stat-card">
                        <div class="stat-label">📅 连续签到</div>
                        <div class="stat-value">?<span style="font-size:12px;">天</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">📊 累计签到</div>
                        <div class="stat-value">?<span style="font-size:12px;">天</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">💎 矿石总数</div>
                        <div class="stat-value">{after_points}<span style="font-size:12px;">个</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">✨ 今日获得</div>
                        <div class="stat-value">{today_ore}<span style="font-size:12px;">矿石</span></div>
                    </div>
                </div>
                
                <div class="result-card">
                    <div class="result-icon sign-icon">✅</div>
                    <div class="result-info">
                        <div class="result-title sign-title">{sign_status}</div>
                        <div class="result-desc">获得 {sign_ore} 矿石</div>
                    </div>
                </div>
                
                <div class="result-card">
                    <div class="result-icon lottery-icon">🎁</div>
                    <div class="result-info">
                        <div class="result-title lottery-title">{lottery_result}</div>
                        <div class="result-desc">{lottery_ore} 矿石</div>
                    </div>
                </div>
            </div>
            <div class="footer">
                ⚡ API直连 · 稳定可靠 ⚡
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_cookie_expired_email():
    """发送Cookie过期通知邮件"""
    current_time = format_china_time()
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: monospace; padding: 20px;">
        <h2>⚠️ 掘金签到 - Cookie已过期</h2>
        <p>检测时间：{current_time}</p>
        <p>请重新获取Cookie并更新GitHub Secrets中的 JUEJIN_COOKIE。</p>
        <p>获取方法：</p>
        <ol>
            <li>打开浏览器无痕模式访问 https://juejin.cn</li>
            <li>登录掘金账号</li>
            <li>F12 → Network → 找到任意请求 → 复制Cookie</li>
        </ol>
        <p>此邮件由自动签到系统发送</p>
    </body>
    </html>
    """
    send_email("⚠️ 掘金签到 Cookie 已过期", html, is_html=True)

def main():
    """主函数"""
    # 随机等待 1-3 分钟
    wait_minutes = random.randint(1, 3)
    print(f"⏳ 随机等待 {wait_minutes} 分钟...")
    time.sleep(wait_minutes * 60)
    
    start_time = format_china_time()
    print(f"[{start_time}] 开始执行掘金签到 (API版)")
    
    # 检查Cookie是否配置
    if not COOKIE:
        print("❌ JUEJIN_COOKIE 未配置")
        return
    
    # 获取签到前矿石数
    before_points = get_current_points()
    print(f"💰 签到前矿石: {before_points}")
    
    if before_points == 0:
        print("⚠️ 获取矿石数失败，Cookie可能已过期")
        send_cookie_expired_email()
        return
    
    # 检查今日是否已签到
    is_signed = check_today_status()
    print(f"📅 今日签到状态: {'已签到' if is_signed else '未签到'}")
    
    sign_ore = 0
    sign_status = "已签到"
    
    if not is_signed:
        # 执行签到
        success, sign_ore = check_in()
        if success:
            sign_status = "签到成功"
        else:
            sign_status = "签到失败"
            send_cookie_expired_email()
            return
    else:
        sign_status = "已签到"
    
    # 执行抽奖
    lottery_result, lottery_ore = lottery_draw()
    
    # 获取签到后矿石数
    after_points = get_current_points()
    print(f"💰 签到后矿石: {after_points}")
    
    # 今日获得 = 签到后 - 签到前
    today_ore = after_points - before_points
    if today_ore < 0:
        today_ore = sign_ore + lottery_ore
    print(f"📊 今日共获得矿石: {today_ore}")
    
    # 发送邮件
    html = create_email_html(sign_status, sign_ore, lottery_result, lottery_ore, today_ore, after_points)
    send_email("掘金签到通知", html, is_html=True)
    
    end_time = format_china_time()
    print(f"[{end_time}] 执行完成")

if __name__ == "__main__":
    main()
