#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掘金社区自动签到脚本 - 混合模式修复版
先用Selenium模拟用户真实操作（访问首页、沸点）
再用最新Cookie调用API接口实现签到和抽奖
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

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

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

# 掘金URL
JUEJIN_URL = "https://juejin.cn/"
HOME_URL = "https://juejin.cn/"
PIN_URL = "https://juejin.cn/pin"
SIGNIN_URL = "https://juejin.cn/user/center/signin"

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
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
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

def setup_driver():
    """配置Chrome浏览器选项"""
    chrome_options = Options()
    
    # 无头模式
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')
    
    # 禁用自动化控制标志
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # 使用 webdriver-manager 自动管理 ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # 隐藏 webdriver 属性
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def parse_cookie_string(cookie_str):
    """将Cookie字符串解析为Selenium需要的格式"""
    cookies = []
    for item in cookie_str.split('; '):
        if '=' in item:
            name, value = item.split('=', 1)
            cookies.append({
                'name': name,
                'value': value,
                'domain': '.juejin.cn'
            })
    return cookies

def add_cookies_to_driver(driver, cookie_str):
    """向浏览器添加Cookie"""
    print("\n🍪 添加Cookie到浏览器...")
    driver.get(JUEJIN_URL)
    time.sleep(2)
    
    cookies = parse_cookie_string(cookie_str)
    success_count = 0
    
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
            success_count += 1
        except Exception as e:
            print(f"  添加cookie {cookie['name']} 失败: {e}")
    
    print(f"✅ 成功添加 {success_count}/{len(cookies)} 个cookie")
    driver.refresh()
    time.sleep(3)
    return success_count > 0

def get_fresh_cookies_from_driver(driver):
    """从Selenium获取最新的Cookie字符串"""
    selenium_cookies = driver.get_cookies()
    cookie_dict = {}
    for cookie in selenium_cookies:
        cookie_dict[cookie['name']] = cookie['value']
    
    # 重新构造Cookie字符串
    cookie_parts = []
    for name, value in cookie_dict.items():
        cookie_parts.append(f"{name}={value}")
    
    cookie_str = '; '.join(cookie_parts)
    print(f"📦 从浏览器获取到 {len(cookie_parts)} 个最新Cookie")
    return cookie_str

def extract_csrf_token(cookie_str):
    """从Cookie中提取CSRF token"""
    match = re.search(r'passport_csrf_token=([^;]+)', cookie_str)
    return match.group(1) if match else None

def simulate_user_behavior(driver):
    """模拟真实用户行为 - 使用Selenium"""
    print("\n🌐 ===== 模拟真实用户行为 ===== ")
    
    try:
        # 1. 访问首页
        print("📱 步骤1: 访问掘金首页...")
        driver.get(HOME_URL)
        time.sleep(random.uniform(2, 4))
        print(f"   页面标题: {driver.title}")
        print(f"   当前URL: {driver.current_url}")
        
        # 随机滚动
        scroll_height = random.randint(300, 800)
        driver.execute_script(f"window.scrollTo(0, {scroll_height});")
        print(f"   📜 向下滚动 {scroll_height}px")
        time.sleep(random.uniform(1, 3))
        
        # 2. 访问沸点页面
        print("\n💬 步骤2: 访问沸点页面...")
        driver.get(PIN_URL)
        time.sleep(random.uniform(2, 4))
        print(f"   页面标题: {driver.title}")
        print(f"   当前URL: {driver.current_url}")
        
        # 随机滚动
        scroll_height = random.randint(300, 800)
        driver.execute_script(f"window.scrollTo(0, {scroll_height});")
        print(f"   📜 向下滚动 {scroll_height}px")
        time.sleep(random.uniform(1, 3))
        
        # 3. 随机浏览一下
        print("\n👀 步骤3: 随机浏览...")
        browse_actions = [
            lambda: driver.find_element(By.TAG_NAME, 'body').send_keys(" "),  # 空格键翻页
            lambda: driver.execute_script("window.scrollTo(0, document.body.scrollHeight);"),  # 滚到底部
            lambda: driver.execute_script("window.scrollTo(0, 0);"),  # 滚回顶部
        ]
        action = random.choice(browse_actions)
        action()
        time.sleep(random.uniform(1, 2))
        
        print("✅ 用户行为模拟完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 模拟用户行为时出错: {e}")
        return False

def make_api_request(session, url, method='GET', data=None, cookie_str=None):
    """发送API请求 - 增强版，检查业务状态码"""
    # 提取CSRF token
    csrf_token = extract_csrf_token(cookie_str if cookie_str else COOKIE)
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Type': 'application/json',
        'Origin': 'https://juejin.cn',
        'Referer': 'https://juejin.cn/',
        'User-Agent': random.choice(USER_AGENTS),
        'Cookie': cookie_str if cookie_str else COOKIE,
        'Sec-Ch-Ua': '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }
    
    # 添加CSRF token（如果存在）
    if csrf_token:
        headers['x-secsdk-csrf-token'] = csrf_token
        headers['X-CSRF-Token'] = csrf_token
    
    print(f"\n📡 请求: {method} {url}")
    if csrf_token:
        print(f"🔑 CSRF Token: {csrf_token[:10]}...")
    
    try:
        if method.upper() == 'GET':
            response = session.get(url, headers=headers, timeout=15)
        else:
            response = session.post(url, headers=headers, json=data or {}, timeout=15)
        
        print(f"📊 HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                # 检查业务状态码
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
                print(f"⚠️ 响应解析失败，原始响应: {response.text[:100]}")
                return None
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

def get_user_info(session, cookie_str):
    """获取用户信息"""
    result = make_api_request(session, GET_USER_INFO_URL, 'GET', cookie_str=cookie_str)
    if result and result.get('err_no') == 0:
        data = result.get('data', {})
        username = data.get('user_name', '未知')
        print(f"👤 当前用户: {username}")
        return username
    return None

def get_current_points(session, cookie_str):
    """获取当前矿石数"""
    result = make_api_request(session, GET_CURRENT_POINT_URL, 'GET', cookie_str=cookie_str)
    if result and result.get('err_no') == 0:
        points = result.get('data', 0)
        print(f"💰 当前矿石: {points}")
        return points
    return 0

def check_today_status(session, cookie_str):
    """检查今天是否已签到"""
    result = make_api_request(session, GET_STATUS_URL, 'GET', cookie_str=cookie_str)
    if result and result.get('err_no') == 0:
        is_signed = result.get('data', False)
        print(f"📅 今日签到状态: {'已签到' if is_signed else '未签到'}")
        return is_signed
    return False

def check_in(session, cookie_str):
    """执行签到"""
    print("\n🔄 执行签到...")
    result = make_api_request(session, CHECK_IN_URL, 'POST', data={}, cookie_str=cookie_str)
    
    if result and result.get('err_no') == 0:
        data = result.get('data', {})
        incr_point = data.get('incr_point', 0)
        total_point = data.get('total_point', 0)
        print(f"✅ 签到成功！获得 {incr_point} 矿石，当前总矿石: {total_point}")
        return True, f"获得 {incr_point} 矿石", incr_point
    else:
        if result and result.get('err_msg'):
            print(f"❌ 签到失败: {result.get('err_msg')}")
            return False, result.get('err_msg'), 0
        return False, "签到失败", 0

def lottery_draw(session, cookie_str):
    """执行抽奖"""
    print("\n🎲 执行抽奖...")
    result = make_api_request(session, LOTTERY_URL, 'POST', data={}, cookie_str=cookie_str)
    
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
            print(f"❌ 抽奖失败: {result.get('err_msg')}")
            return f"抽奖失败: {result.get('err_msg')}"
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
                    <span>混合模式修复版</span>
                    <span class="dot"></span>
                    <span>首页·沸点·签到·抽奖</span>
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
                    ⚡ 修复版 · 稳定可靠 ⚡
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_cookie_expired_email():
    """发送Cookie过期通知邮件"""
    try:
        current_time = format_china_time()
        subject = "⚠️ 掘金签到 Cookie 已过期"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Microsoft YaHei', sans-serif;
                    padding: 20px;
                    background-color: #f0f2f5;
                }}
                .container {{
                    max-width: 500px;
                    margin: 0 auto;
                    background: #ffffff;
                    border-radius: 16px;
                    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #ef4444, #dc2626);
                    color: white;
                    padding: 24px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    padding: 24px;
                }}
                .warning-icon {{
                    font-size: 48px;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .message {{
                    background: #fef2f2;
                    border-left: 4px solid #ef4444;
                    padding: 16px;
                    margin-bottom: 20px;
                    border-radius: 8px;
                }}
                .message p {{
                    margin: 8px 0;
                    color: #1e293b;
                }}
                .time {{
                    color: #64748b;
                    font-size: 14px;
                    text-align: center;
                    margin-top: 20px;
                }}
                .footer {{
                    background: #f8fafc;
                    padding: 16px;
                    text-align: center;
                    color: #64748b;
                    font-size: 12px;
                    border-top: 1px solid #e2e8f0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⛏️ 掘金签到</h1>
                </div>
                <div class="content">
                    <div class="warning-icon">⚠️</div>
                    <div class="message">
                        <p><strong>Cookie 已过期</strong></p>
                        <p>自动签到脚本无法登录掘金，因为存储的 Cookie 已经失效。</p>
                        <p>请重新获取 Cookie 并更新 GitHub Secrets 中的 JUEJIN_COOKIE。</p>
                    </div>
                    <p class="time">⏱️ 检测时间：{current_time}</p>
                </div>
                <div class="footer">
                    <p>🤖 此邮件由自动签到系统发送</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=30)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        server.quit()
        print("✅ Cookie过期通知邮件发送成功")
        return True
    except Exception as e:
        print(f"❌ Cookie过期邮件发送失败: {e}")
        return False

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
    print(f"[{start_time}] 开始执行掘金签到 (混合模式修复版)")

    if not check_config():
        return

    driver = None
    sign_status = "失败"
    sign_detail = "未知错误"
    lottery_result = "未执行"
    user_stats = {'连续签到': '未知', '累计签到': '未知', '矿石总数': '0', '今日获得': '0'}

    try:
        # ===== 第一步：使用Selenium模拟用户行为 =====
        print("\n🌐 ===== 第一阶段：Selenium模拟用户操作 =====")
        print("正在启动Chrome浏览器...")
        driver = setup_driver()
        
        # 添加Cookie
        add_cookies_to_driver(driver, COOKIE)
        
        # 模拟用户行为（访问首页、沸点、随机浏览）
        simulate_success = simulate_user_behavior(driver)
        
        if not simulate_success:
            print("⚠️ 用户行为模拟部分失败，继续使用当前会话")
        
        # 从浏览器获取最新的Cookie
        print("\n🔍 从浏览器获取最新Cookie...")
        fresh_cookie = get_fresh_cookies_from_driver(driver)
        
        # 关闭浏览器，释放资源
        print("\n🔚 关闭浏览器...")
        driver.quit()
        driver = None
        
        # 随机延迟，模拟人类操作间隔
        time.sleep(random.uniform(2, 5))
        
        # ===== 第二步：使用最新Cookie执行API签到和抽奖 =====
        print("\n🚀 ===== 第二阶段：API执行签到抽奖 =====")
        
        # 创建session
        session = requests.Session()
        
        # 先测试Cookie有效性
        print("\n🔍 测试Cookie有效性...")
        test_result = make_api_request(session, GET_USER_INFO_URL, 'GET', cookie_str=fresh_cookie)
        if not test_result or test_result.get('err_no') != 0:
            print("❌ Cookie无效或已过期，尝试使用原始Cookie...")
            test_result = make_api_request(session, GET_USER_INFO_URL, 'GET', cookie_str=COOKIE)
            if not test_result or test_result.get('err_no') != 0:
                print("❌ 所有Cookie均无效，发送过期通知")
                send_cookie_expired_email()
                return
            else:
                fresh_cookie = COOKIE
                print("✅ 原始Cookie有效，继续使用")
        
        # 获取用户信息
        username = get_user_info(session, fresh_cookie)
        if username:
            print(f"👋 欢迎 {username}")
        
        # 获取当前矿石数
        current_points = get_current_points(session, fresh_cookie)
        user_stats['矿石总数'] = str(current_points)
        
        # 检查今日签到状态
        is_signed = check_today_status(session, fresh_cookie)
        
        # 执行签到/抽奖
        if not is_signed:
            # 执行签到
            sign_success, sign_detail, sign_ore = check_in(session, fresh_cookie)
            
            if sign_success:
                sign_status = "签到成功"
                user_stats['今日获得'] = str(sign_ore)
                
                # 重新获取矿石数
                time.sleep(random.uniform(1, 3))
                current_points = get_current_points(session, fresh_cookie)
                user_stats['矿石总数'] = str(current_points)
                
                # 执行抽奖
                time.sleep(random.uniform(1, 3))
                lottery_result = lottery_draw(session, fresh_cookie)
                
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
            lottery_result = lottery_draw(session, fresh_cookie)
            
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
        # 确保浏览器被关闭
        if driver:
            driver.quit()
            print("浏览器已关闭")

        # 发送邮件
        html_content = create_email_html(sign_status, sign_detail, lottery_result, user_stats)
        send_email("掘金签到通知 - 混合模式修复版", html_content, is_html=True)

        end_time = format_china_time()
        print(f"[{end_time}] 执行完成")

if __name__ == "__main__":
    main()
