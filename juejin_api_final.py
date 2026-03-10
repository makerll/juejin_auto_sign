#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掘金社区自动签到脚本 - API终极稳定版
完全使用API，添加完整请求头和Cookie处理
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
GET_USER_INFO_URL = f"{BASE_URL}/user_api/v1/user/get"

# 随机User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

def check_config():
    """检查必要的配置"""
    missing = []
    if not COOKIE:
        missing.append('JUEJIN_COOKIE')
    if not EMAIL_FROM:
        missing.append('EMAIL_FROM')
    if not EMAIL_PASSWORD:
        missing.append('EMAIL_PASSWORD')
    if missing:
        print("错误：以下配置缺失：", missing)
        return False
    return True

def get_china_time():
    """获取中国时间"""
    china_tz = timezone(timedelta(hours=8))
    return datetime.now(china_tz)

def format_china_time():
    """格式化中国时间"""
    return get_china_time().strftime('%Y-%m-%d %H:%M:%S')

def extract_csrf_token():
    """从Cookie中提取CSRF token"""
    match = re.search(r'passport_csrf_token=([^;]+)', COOKIE)
    return match.group(1) if match else None

def make_api_request(url, method='POST', data=None):
    """发送API请求"""
    csrf_token = extract_csrf_token()
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Type': 'application/json',
        'Origin': 'https://juejin.cn',
        'Referer': 'https://juejin.cn/',
        'User-Agent': random.choice(USER_AGENTS),
        'Cookie': COOKIE,
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }
    
    # 添加CSRF token
    if csrf_token:
        headers['x-secsdk-csrf-token'] = csrf_token
        headers['X-CSRF-Token'] = csrf_token
    
    print(f"\n📡 请求: {method} {url}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=15)
        else:
            response = requests.post(url, headers=headers, json=data or {}, timeout=15)
        
        print(f"📊 HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            if response.text:
                try:
                    result = response.json()
                    err_no = result.get('err_no')
                    if err_no == 0:
                        print(f"✅ API请求成功")
                        return result
                    elif err_no == 403:
                        print(f"❌ 需要登录: {result.get('err_msg')}")
                        return None
                    else:
                        print(f"⚠️ API错误: {result.get('err_msg')} (err_no={err_no})")
                        return result
                except:
                    print(f"⚠️ 响应解析失败，原始响应为空")
                    return None
            else:
                print(f"⚠️ 响应内容为空")
                return None
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

def get_user_info():
    """获取用户信息"""
    result = make_api_request(GET_USER_INFO_URL, 'GET')
    if result and result.get('err_no') == 0:
        data = result.get('data', {})
        username = data.get('user_name', '未知')
        print(f"👤 当前用户: {username}")
        return username
    return None

def get_current_points():
    """获取当前矿石数"""
    result = make_api_request(GET_CURRENT_POINT_URL, 'GET')
    if result and result.get('err_no') == 0:
        points = result.get('data', 0)
        print(f"💰 当前矿石: {points}")
        return points
    return 0

def check_today_status():
    """检查今天是否已签到"""
    result = make_api_request(GET_STATUS_URL, 'GET')
    if result and result.get('err_no') == 0:
        is_signed = result.get('data', False)
        print(f"📅 今日签到状态: {'已签到' if is_signed else '未签到'}")
        return is_signed
    return False

def check_in():
    """执行签到"""
    print("\n🔄 执行签到...")
    result = make_api_request(CHECK_IN_URL, 'POST', {})
    
    if result and result.get('err_no') == 0:
        data = result.get('data', {})
        incr_point = data.get('incr_point', 0)
        total_point = data.get('total_point', 0)
        print(f"✅ 签到成功！获得 {incr_point} 矿石，当前总矿石: {total_point}")
        return True, f"获得 {incr_point} 矿石", incr_point
    else:
        return False, "签到失败", 0

def lottery_draw():
    """执行抽奖"""
    print("\n🎲 执行抽奖...")
    result = make_api_request(LOTTERY_URL, 'POST', {})
    
    if result and result.get('err_no') == 0:
        data = result.get('data', {})
        lottery_name = data.get('lottery_name', '未知')
        print(f"🎉 抽奖获得: {lottery_name}")
        return lottery_name
    else:
        if result and result.get('err_msg'):
            if '今天已经抽过奖' in result.get('err_msg'):
                print("⏰ 今天已经抽过奖了")
                return "今天已经抽过奖"
        return "抽奖失败"

def send_email(subject, content, is_html=False):
    """发送邮件通知"""
    try:
        if not all([EMAIL_FROM, EMAIL_PASSWORD, SMTP_SERVER]):
            print("邮件配置不完整，跳过邮件发送")
            return False

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
        print(f"✅ 邮件发送成功")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False

def create_email_html(sign_status, sign_detail, lottery_result, user_stats):
    """创建HTML邮件内容"""
    current_time = format_china_time()

    # 签到状态
    if "成功" in sign_status:
        sign_badge = "✨ 签到成功"
        sign_color = "#10b981"
    elif "已签到" in sign_status:
        sign_badge = "📌 今日已签"
        sign_color = "#3b82f6"
    else:
        sign_badge = "⚠️ 签到异常"
        sign_color = "#ef4444"

    # 抽奖结果
    if "获得" in lottery_result and "矿石" in lottery_result:
        lottery_icon = "🎁"
        lottery_badge = "矿石奖励"
        lottery_color = "#8b5cf6"
    elif "获得" in lottery_result:
        lottery_icon = "🎁"
        lottery_badge = "恭喜中奖"
        lottery_color = "#8b5cf6"
    elif "今天已经抽过" in lottery_result:
        lottery_icon = "⏰"
        lottery_badge = "今日已抽"
        lottery_color = "#f59e0b"
    else:
        lottery_icon = "❓"
        lottery_badge = "抽奖完成"
        lottery_color = "#6b7280"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 16px;
            }}
            .card {{
                max-width: 480px;
                width: 100%;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 32px;
                box-shadow: 0 20px 40px -12px rgba(0, 20, 40, 0.25);
                overflow: hidden;
            }}
            .header {{
                padding: 24px 24px 16px;
                background: linear-gradient(112deg, #1E80FF, #0052CC);
                color: white;
            }}
            .title-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }}
            .title {{
                font-size: 20px;
                font-weight: 600;
                color: white;
            }}
            .date-badge {{
                font-size: 13px;
                color: rgba(255,255,255,0.9);
                background: rgba(255,255,255,0.2);
                padding: 4px 10px;
                border-radius: 40px;
            }}
            .sub-title {{
                font-size: 13px;
                color: rgba(255,255,255,0.9);
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .dot {{
                width: 4px;
                height: 4px;
                background: rgba(255,255,255,0.5);
                border-radius: 50%;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
                padding: 20px 24px;
                background: #ffffff;
            }}
            .stat-item {{
                background: #f8fafc;
                border-radius: 20px;
                padding: 14px 12px;
                border: 1px solid #f1f5f9;
            }}
            .stat-label {{
                font-size: 12px;
                color: #64748b;
                margin-bottom: 6px;
            }}
            .stat-value {{
                font-size: 22px;
                font-weight: 600;
                color: #0f172a;
            }}
            .stat-unit {{
                font-size: 12px;
                font-weight: 400;
                color: #94a3b8;
                margin-left: 2px;
            }}
            .content {{
                padding: 8px 24px 24px;
            }}
            .status-card {{
                background: #ffffff;
                border-radius: 24px;
                padding: 18px;
                margin-bottom: 12px;
                border: 1px solid #f1f5f9;
            }}
            .status-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }}
            .status-title {{
                font-size: 13px;
                font-weight: 500;
                color: #64748b;
            }}
            .status-badge {{
                font-size: 12px;
                padding: 4px 10px;
                border-radius: 30px;
                background: #f1f5f9;
                color: #475569;
            }}
            .status-main {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .status-icon {{
                width: 40px;
                height: 40px;
                background: {sign_color}10;
                border-radius: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 22px;
            }}
            .status-info {{
                flex: 1;
            }}
            .status-line {{
                font-weight: 600;
                font-size: 16px;
                color: {sign_color};
                margin-bottom: 4px;
            }}
            .status-desc {{
                font-size: 13px;
                color: #64748b;
            }}
            .lottery-card {{
                background: linear-gradient(105deg, {lottery_color}05, #ffffff);
                border-radius: 24px;
                padding: 18px;
                border: 1px solid {lottery_color}20;
            }}
            .lottery-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
            }}
            .lottery-title {{
                font-size: 13px;
                font-weight: 500;
                color: #64748b;
            }}
            .lottery-badge {{
                font-size: 12px;
                padding: 4px 10px;
                border-radius: 30px;
                background: {lottery_color}10;
                color: {lottery_color};
            }}
            .lottery-content {{
                display: flex;
                align-items: center;
                gap: 14px;
            }}
            .lottery-icon {{
                width: 44px;
                height: 44px;
                background: {lottery_color}15;
                border-radius: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 26px;
            }}
            .lottery-info {{
                flex: 1;
            }}
            .lottery-result {{
                font-weight: 600;
                font-size: 18px;
                color: {lottery_color};
                margin-bottom: 2px;
            }}
            .lottery-note {{
                font-size: 12px;
                color: #94a3b8;
            }}
            .footer {{
                padding: 16px 24px 20px;
                text-align: center;
                border-top: 1px solid #f1f5f9;
                background: #ffffff;
            }}
            .footer-text {{
                font-size: 12px;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div class="title-row">
                    <span class="title">⛏️ 掘金签到</span>
                    <span class="date-badge">{current_time}</span>
                </div>
                <div class="sub-title">
                    <span>API终极稳定版</span>
                    <span class="dot"></span>
                    <span>无需浏览器</span>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">📅 连续</div>
                    <div class="stat-value">{user_stats['连续签到']}<span class="stat-unit">天</span></div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">📊 累计</div>
                    <div class="stat-value">{user_stats['累计签到']}<span class="stat-unit">天</span></div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">💎 矿石</div>
                    <div class="stat-value">{user_stats['矿石总数']}<span class="stat-unit">个</span></div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">✨ 今日</div>
                    <div class="stat-value">{user_stats['今日获得']}<span class="stat-unit">矿石</span></div>
                </div>
            </div>
            
            <div class="content">
                <div class="status-card">
                    <div class="status-header">
                        <span class="status-title">✍️ 签到状态</span>
                        <span class="status-badge">{sign_badge}</span>
                    </div>
                    <div class="status-main">
                        <div class="status-icon" style="background: {sign_color}10;">{"✅" if "成功" in sign_status or "已签到" in sign_status else "⚠️"}</div>
                        <div class="status-info">
                            <div class="status-line">{sign_status}</div>
                            <div class="status-desc">{sign_detail}</div>
                        </div>
                    </div>
                </div>
                
                <div class="lottery-card">
                    <div class="lottery-header">
                        <span class="lottery-title">🎲 免费抽奖</span>
                        <span class="lottery-badge">{lottery_badge}</span>
                    </div>
                    <div class="lottery-content">
                        <div class="lottery-icon" style="background: {lottery_color}15;">{lottery_icon}</div>
                        <div class="lottery-info">
                            <div class="lottery-result">{lottery_result}</div>
                            <div class="lottery-note">今日免费机会已使用</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <div class="footer-text">
                    ⚡ API直连 · 快速稳定 ⚡
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def main():
    """主函数"""
    # ================= 随机等待逻辑 (1-3 分钟) =================
    wait_minutes = random.randint(1, 3)
    wait_seconds = wait_minutes * 60
    
    start_time = time.strftime("%H:%M:%S")
    end_time_obj = time.time() + wait_seconds
    end_time_str = time.strftime("%H:%M:%S", time.localtime(end_time_obj))
    
    print(f"🤖 [Juejin Bot] 任务已启动: {start_time}")
    print(f"🎲 [随机策略] 生成随机等待时间: {wait_minutes} 分钟")
    print(f"⏳ [预计执行] 将在约 {end_time_str} 开始签到...")
    print("-" * 30)
    
    time.sleep(wait_seconds)
    
    print("-" * 30)
    print(f"✅ [唤醒] 等待结束，当前时间: {time.strftime('%H:%M:%S')}")
    print("🚀 开始执行签到逻辑...")
    # =========================================================

    start_time = format_china_time()
    print(f"[{start_time}] 开始执行掘金签到 (API终极稳定版)")

    if not check_config():
        return

    sign_status = "失败"
    sign_detail = "未知错误"
    lottery_result = "未执行"
    user_stats = {'连续签到': '未知', '累计签到': '未知', '矿石总数': '0', '今日获得': '0'}

    try:
        # 获取用户信息验证Cookie
        username = get_user_info()
        if not username:
            print("❌ Cookie无效，请重新获取")
            return
        
        # 获取当前矿石数
        current_points = get_current_points()
        user_stats['矿石总数'] = str(current_points)
        
        # 检查今日签到状态
        is_signed = check_today_status()
        
        if not is_signed:
            # 执行签到
            sign_success, sign_detail, sign_ore = check_in()
            
            if sign_success:
                sign_status = "签到成功"
                user_stats['今日获得'] = str(sign_ore)
                
                # 重新获取矿石数
                time.sleep(random.uniform(1, 3))
                current_points = get_current_points()
                user_stats['矿石总数'] = str(current_points)
                
                # 执行抽奖
                time.sleep(random.uniform(1, 3))
                lottery_result = lottery_draw()
                
                # 如果是矿石，累加到今日获得
                if "矿石" in lottery_result:
                    ore_match = re.search(r'(\d+)', lottery_result)
                    if ore_match:
                        lottery_ore = int(ore_match.group(1))
                        current_total = int(user_stats['今日获得'] or 0)
                        user_stats['今日获得'] = str(current_total + lottery_ore)
            else:
                sign_status = "签到失败"
                lottery_result = "签到失败，未抽奖"
        else:
            sign_status = "已签到"
            sign_detail = "今日已完成签到"
            
            # 已签到，直接抽奖
            time.sleep(random.uniform(1, 3))
            lottery_result = lottery_draw()
            
            # 如果是矿石，记录今日获得
            if "矿石" in lottery_result:
                ore_match = re.search(r'(\d+)', lottery_result)
                if ore_match:
                    lottery_ore = int(ore_match.group(1))
                    user_stats['今日获得'] = str(lottery_ore)

        print(f"\n📊 最终结果 - 签到: {sign_status}, 抽奖: {lottery_result}")

    except Exception as e:
        error_msg = str(e)
        print(f"❌ 执行过程中出现异常: {error_msg}")
        sign_detail = f"异常: {error_msg[:100]}"

    finally:
        # 发送邮件
        html_content = create_email_html(sign_status, sign_detail, lottery_result, user_stats)
        send_email("掘金签到通知 - API终极稳定版", html_content, is_html=True)

        end_time = format_china_time()
        print(f"[{end_time}] 执行完成")

if __name__ == "__main__":
    main()
