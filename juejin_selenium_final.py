#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掘金社区自动签到脚本 - 纯Selenium最终版
全新邮件设计 + 完善的抽奖处理
"""
import os
import time
import random
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
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

def setup_driver():
    """配置Chrome浏览器选项"""
    chrome_options = Options()
    
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')
    
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 禁用图片加载
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_page_load_timeout(30)
    
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
    time.sleep(3)
    
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

def safe_click(driver, element, description="元素"):
    """安全点击元素"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(1)
        
        try:
            element.click()
            print(f"✅ 点击{description}成功（常规点击）")
            return True
        except:
            try:
                driver.execute_script("arguments[0].click();", element)
                print(f"✅ 点击{description}成功（JavaScript点击）")
                return True
            except:
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(element).click().perform()
                    print(f"✅ 点击{description}成功（ActionChains点击）")
                    return True
                except:
                    return False
    except Exception as e:
        print(f"❌ 点击{description}失败: {e}")
        return False

def simulate_user_behavior(driver):
    """模拟真实用户行为"""
    print("\n🌐 ===== 模拟真实用户行为 ===== ")
    
    try:
        # 访问首页
        print("📱 步骤1: 访问掘金首页...")
        driver.get(HOME_URL)
        time.sleep(random.uniform(2, 4))
        scroll_height = random.randint(300, 800)
        driver.execute_script(f"window.scrollTo(0, {scroll_height});")
        print(f"   📜 向下滚动 {scroll_height}px")
        time.sleep(random.uniform(1, 3))
        
        # 访问沸点
        print("\n💬 步骤2: 访问沸点页面...")
        driver.get(PIN_URL)
        time.sleep(random.uniform(2, 4))
        scroll_height = random.randint(300, 800)
        driver.execute_script(f"window.scrollTo(0, {scroll_height});")
        print(f"   📜 向下滚动 {scroll_height}px")
        time.sleep(random.uniform(1, 3))
        
        # 返回签到页
        print("\n📅 步骤3: 返回签到页面...")
        driver.get(SIGNIN_URL)
        time.sleep(3)
        
        print("✅ 用户行为模拟完成")
        return True
    except Exception as e:
        print(f"⚠️ 模拟用户行为时出错: {e}")
        return False

def get_user_stats(driver):
    """从页面获取用户统计信息"""
    stats = {'连续签到': '未知', '累计签到': '未知', '矿石总数': '0', '今日获得': '0'}

    try:
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        
        # 连续签到
        match = re.search(r'(\d+)\s*(?:天)?\s*连续签到天数', page_text)
        if not match:
            match = re.search(r'(\d+)[^\d]*连续', page_text)
        if match:
            stats['连续签到'] = match.group(1)

        # 累计签到
        match = re.search(r'(\d+)\s*(?:天)?\s*累计签到天数', page_text)
        if not match:
            match = re.search(r'(\d+)[^\d]*累计', page_text)
        if match:
            stats['累计签到'] = match.group(1)

        # 矿石总数
        ore_matches = re.findall(r'(\d{4,7})\s*矿石', page_text)
        if ore_matches:
            stats['矿石总数'] = ore_matches[0]
        else:
            all_numbers = re.findall(r'\b(\d{4,7})\b', page_text)
            valid_ores = [n for n in all_numbers if not (2020 <= int(n) <= 2030)]
            if valid_ores:
                stats['矿石总数'] = max(valid_ores, key=int)

    except Exception as e:
        print(f"获取用户统计信息时出错: {e}")

    return stats

def check_and_click_sign(driver):
    """检查并点击签到按钮"""
    print("\n🔍 检查签到状态...")
    
    try:
        # 检查是否已签到
        signed_elements = driver.find_elements(By.XPATH, '//*[contains(text(), "今日已签到")]')
        for element in signed_elements:
            if element.is_displayed():
                print("✅ 今日已签到")
                return True, "已签到", None, 0
        
        # 查找签到按钮
        button_selectors = [
            '//button[contains(text(), "立即签到")]',
            '//button[contains(text(), "签到")]',
            '//div[contains(text(), "立即签到")]',
            '.signin-btn',
            '.check-in-btn',
        ]
        
        for selector in button_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        print(f"✅ 找到签到按钮: {element.text}")
                        
                        if safe_click(driver, element, "签到按钮"):
                            print("⏳ 等待签到结果...")
                            time.sleep(5)
                            
                            # 检查弹窗并提取奖励
                            try:
                                popup = driver.find_element(By.XPATH, '//*[contains(text(), "签到成功") or contains(text(), "获得")]')
                                if popup.is_displayed():
                                    popup_text = popup.text
                                    print(f"🎉 签到成功弹窗: {popup_text}")
                                    
                                    ore_match = re.search(r'(\d+)', popup_text)
                                    if ore_match:
                                        ore_count = int(ore_match.group(1))
                                        reward = f"获得 {ore_count} 矿石"
                                        return True, reward, element, ore_count
                            except:
                                pass
                            
                            return True, "签到成功", element, 0
            except:
                continue
        
        print("❌ 未找到签到按钮")
        return False, "未找到签到按钮", None, 0
        
    except Exception as e:
        print(f"❌ 检查签到状态时出错: {e}")
        return False, f"错误: {str(e)}", None, 0

def check_and_click_lottery(driver):
    """检查并点击抽奖，返回奖品信息"""
    print("\n🎲 检查抽奖机会...")
    
    try:
        # 切换到抽奖页面
        lottery_tab_selectors = [
            '//*[contains(text(), "幸运抽奖")]',
            '//div[@role="tab" and contains(text(), "幸运抽奖")]',
            '.lottery-tab',
        ]
        
        for selector in lottery_tab_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed():
                        print(f"✅ 找到幸运抽奖标签: {element.text}")
                        safe_click(driver, element, "幸运抽奖标签")
                        time.sleep(3)
                        break
            except:
                continue
        
        # 查找抽奖按钮
        lottery_selectors = [
            '//*[contains(text(), "去抽奖")]',
            '//*[contains(text(), "免费抽奖")]',
            '//button[contains(text(), "抽奖")]',
            '.lottery-btn',
            '.draw-btn',
        ]
        
        for selector in lottery_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        print(f"✅ 找到抽奖按钮: {element.text}")
                        
                        if safe_click(driver, element, "抽奖按钮"):
                            print("⏳ 等待抽奖结果...")
                            time.sleep(5)
                            
                            # 获取抽奖结果
                            page_text = driver.find_element(By.TAG_NAME, 'body').text
                            
                            # 1. 检查是否获得矿石（带数字）
                            ore_match = re.search(r'获得[：:]\s*(\d+)\s*矿石', page_text)
                            if ore_match:
                                ore_count = int(ore_match.group(1))
                                prize_name = f"获得 {ore_count} 矿石"
                                print(f"🎉 抽中 {prize_name}")
                                return {
                                    'type': 'ore',
                                    'name': prize_name,
                                    'value': ore_count,
                                    'display': f'🎁 {prize_name}'
                                }
                            
                            ore_match2 = re.search(r'抽中[“”]?(\d+)\s*矿石', page_text)
                            if ore_match2:
                                ore_count = int(ore_match2.group(1))
                                prize_name = f"获得 {ore_count} 矿石"
                                print(f"🎉 抽中 {prize_name}")
                                return {
                                    'type': 'ore',
                                    'name': prize_name,
                                    'value': ore_count,
                                    'display': f'🎁 {prize_name}'
                                }
                            
                            # 2. 检查是否获得实物奖品
                            prize_match = re.search(r'获得[：:]\s*([^\n，。,.]+)', page_text)
                            if prize_match:
                                prize = prize_match.group(1).strip()
                                # 常见奖品映射
                                prize_emojis = {
                                    '盲盒': '📦',
                                    '小夜灯': '💡',
                                    '耳机': '🎧',
                                    '兑换券': '🎫',
                                    '唇膏': '💄',
                                    '抱枕': '🛏️',
                                    '徽章': '🏅',
                                    '贴纸': '📋',
                                }
                                emoji = '🎁'
                                for key, value in prize_emojis.items():
                                    if key in prize:
                                        emoji = value
                                        break
                                print(f"🎉 抽中实物奖品: {prize}")
                                return {
                                    'type': 'physical',
                                    'name': prize,
                                    'value': 0,
                                    'display': f'{emoji} {prize}'
                                }
                            
                            # 3. 检查是否谢谢参与
                            if '谢谢参与' in page_text:
                                print("🍀 谢谢参与")
                                return {
                                    'type': 'none',
                                    'name': '谢谢参与',
                                    'value': 0,
                                    'display': '🍀 谢谢参与'
                                }
                            
                            # 4. 默认情况
                            return {
                                'type': 'unknown',
                                'name': '抽奖完成',
                                'value': 0,
                                'display': '🎲 抽奖完成'
                            }
            except:
                continue
        
        print("⏰ 未找到抽奖按钮，可能今天已抽过")
        return {
            'type': 'already',
            'name': '今天已经抽过奖',
            'value': 0,
            'display': '⏰ 今天已经抽过奖'
        }
        
    except Exception as e:
        print(f"❌ 抽奖过程出错: {e}")
        return {
            'type': 'error',
            'name': '抽奖失败',
            'value': 0,
            'display': '❌ 抽奖失败'
        }

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

def create_email_html(sign_status, sign_detail, lottery_info, user_stats):
    """创建HTML邮件内容 - 清新优雅设计"""
    current_time = format_china_time()

    # 签到状态样式
    if "成功" in sign_status:
        sign_icon = "✨"
        sign_color = "#10b981"
        sign_text = "签到成功"
    elif "已签到" in sign_status:
        sign_icon = "📌"
        sign_color = "#3b82f6"
        sign_text = "今日已签"
    else:
        sign_icon = "⚠️"
        sign_color = "#ef4444"
        sign_text = "签到异常"

    # 抽奖信息
    lottery_display = lottery_info['display']
    
    # 根据抽奖类型设置不同的样式
    if lottery_info['type'] == 'ore':
        lottery_bg = "#f0f9ff"
        lottery_border = "#3b82f6"
    elif lottery_info['type'] == 'physical':
        lottery_bg = "#fef3c7"
        lottery_border = "#f59e0b"
    elif lottery_info['type'] == 'none':
        lottery_bg = "#f1f5f9"
        lottery_border = "#94a3b8"
    else:
        lottery_bg = "#f1f5f9"
        lottery_border = "#94a3b8"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>掘金签到</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', 'Microsoft YaHei', sans-serif;
                background: linear-gradient(145deg, #f8fafc 0%, #eef2f6 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .card {{
                max-width: 500px;
                width: 100%;
                background: rgba(255, 255, 255, 0.98);
                backdrop-filter: blur(10px);
                border-radius: 40px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15);
                overflow: hidden;
                transition: transform 0.2s ease;
            }}
            
            .card:hover {{
                transform: translateY(-4px);
            }}
            
            /* 头部 */
            .header {{
                padding: 32px 28px 20px;
                background: linear-gradient(135deg, #ffffff 0%, #f9fafc 100%);
                border-bottom: 1px solid rgba(0, 0, 0, 0.03);
            }}
            
            .title-section {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
            }}
            
            .title {{
                font-size: 28px;
                font-weight: 700;
                background: linear-gradient(135deg, #1e293b, #0f172a);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.5px;
            }}
            
            .date-badge {{
                background: #f1f5f9;
                color: #475569;
                padding: 8px 16px;
                border-radius: 40px;
                font-size: 14px;
                font-weight: 500;
                letter-spacing: 0.3px;
            }}
            
            .subtitle {{
                display: flex;
                align-items: center;
                gap: 8px;
                color: #64748b;
                font-size: 14px;
                font-weight: 400;
            }}
            
            .dot {{
                width: 4px;
                height: 4px;
                background: #cbd5e1;
                border-radius: 50%;
            }}
            
            /* 统计卡片网格 */
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                padding: 24px 28px;
                background: #ffffff;
            }}
            
            .stat-card {{
                background: #f8fafc;
                border-radius: 28px;
                padding: 20px 16px;
                border: 1px solid #f1f5f9;
                transition: all 0.2s;
            }}
            
            .stat-card:hover {{
                border-color: #cbd5e1;
                background: #ffffff;
            }}
            
            .stat-label {{
                font-size: 13px;
                color: #64748b;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                gap: 4px;
            }}
            
            .stat-value {{
                font-size: 28px;
                font-weight: 700;
                color: #0f172a;
                line-height: 1.2;
            }}
            
            .stat-unit {{
                font-size: 14px;
                font-weight: 400;
                color: #94a3b8;
                margin-left: 4px;
            }}
            
            /* 内容区域 */
            .content {{
                padding: 8px 28px 28px;
            }}
            
            /* 签到卡片 */
            .sign-card {{
                background: linear-gradient(105deg, {sign_color}05, #ffffff);
                border-radius: 28px;
                padding: 20px;
                margin-bottom: 16px;
                border: 1px solid {sign_color}20;
            }}
            
            .sign-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
            }}
            
            .sign-title {{
                font-size: 14px;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            .sign-badge {{
                background: {sign_color}10;
                color: {sign_color};
                padding: 6px 14px;
                border-radius: 40px;
                font-size: 13px;
                font-weight: 500;
            }}
            
            .sign-main {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            
            .sign-icon {{
                width: 52px;
                height: 52px;
                background: {sign_color}10;
                border-radius: 26px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
            }}
            
            .sign-info {{
                flex: 1;
            }}
            
            .sign-line {{
                font-weight: 600;
                font-size: 18px;
                color: {sign_color};
                margin-bottom: 4px;
            }}
            
            .sign-desc {{
                font-size: 14px;
                color: #64748b;
            }}
            
            /* 抽奖卡片 */
            .lottery-card {{
                background: {lottery_bg};
                border-radius: 28px;
                padding: 20px;
                border: 1px solid {lottery_border}30;
            }}
            
            .lottery-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
            }}
            
            .lottery-title {{
                font-size: 14px;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            .lottery-badge {{
                background: {lottery_border}15;
                color: {lottery_border};
                padding: 6px 14px;
                border-radius: 40px;
                font-size: 13px;
                font-weight: 500;
            }}
            
            .lottery-content {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            
            .lottery-icon {{
                width: 52px;
                height: 52px;
                background: {lottery_border}10;
                border-radius: 26px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
            }}
            
            .lottery-info {{
                flex: 1;
            }}
            
            .lottery-result {{
                font-weight: 600;
                font-size: 18px;
                color: {lottery_border};
                margin-bottom: 4px;
            }}
            
            .lottery-note {{
                font-size: 13px;
                color: #64748b;
            }}
            
            /* 底部 */
            .footer {{
                padding: 20px 28px 28px;
                text-align: center;
                border-top: 1px solid #f1f5f9;
                background: #ffffff;
            }}
            
            .footer-text {{
                font-size: 13px;
                color: #94a3b8;
                line-height: 1.6;
            }}
            
            .footer-highlight {{
                color: #1E80FF;
                font-weight: 500;
            }}
            
            .separator {{
                width: 100%;
                height: 1px;
                background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
                margin: 16px 0;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <!-- 头部 -->
            <div class="header">
                <div class="title-section">
                    <span class="title">⛏️ 掘金签到</span>
                    <span class="date-badge">{current_time[5:10]} {current_time[11:16]}</span>
                </div>
                <div class="subtitle">
                    <span>每日自动签到</span>
                    <span class="dot"></span>
                    <span>免费抽奖1次</span>
                    <span class="dot"></span>
                    <span>纯Selenium</span>
                </div>
            </div>
            
            <!-- 统计卡片网格 -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">📅 连续签到</div>
                    <div class="stat-value">{user_stats['连续签到']}<span class="stat-unit">天</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">📊 累计签到</div>
                    <div class="stat-value">{user_stats['累计签到']}<span class="stat-unit">天</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">💎 矿石总数</div>
                    <div class="stat-value">{user_stats['矿石总数']}<span class="stat-unit">个</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">✨ 今日获得</div>
                    <div class="stat-value">{user_stats['今日获得']}<span class="stat-unit">矿石</span></div>
                </div>
            </div>
            
            <!-- 内容区域 -->
            <div class="content">
                <!-- 签到卡片 -->
                <div class="sign-card">
                    <div class="sign-header">
                        <span class="sign-title">✍️ 签到状态</span>
                        <span class="sign-badge">{sign_text}</span>
                    </div>
                    <div class="sign-main">
                        <div class="sign-icon">{sign_icon}</div>
                        <div class="sign-info">
                            <div class="sign-line">{sign_status}</div>
                            <div class="sign-desc">{sign_detail}</div>
                        </div>
                    </div>
                </div>
                
                <!-- 抽奖卡片 -->
                <div class="lottery-card">
                    <div class="lottery-header">
                        <span class="lottery-title">🎲 免费抽奖</span>
                        <span class="lottery-badge">今日机会</span>
                    </div>
                    <div class="lottery-content">
                        <div class="lottery-icon">{lottery_display[0]}</div>
                        <div class="lottery-info">
                            <div class="lottery-result">{lottery_display[2:] if lottery_display.startswith(('🎁', '🎲', '🍀', '⏰', '❌')) else lottery_display}</div>
                            <div class="lottery-note">{
                                'ore' if lottery_info['type'] == 'ore' else
                                '实物奖品' if lottery_info['type'] == 'physical' else
                                '未中奖' if lottery_info['type'] == 'none' else
                                '今日已抽' if lottery_info['type'] == 'already' else
                                '抽奖状态'
                            }</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 底部 -->
            <div class="footer">
                <div class="footer-text">
                    <span class="footer-highlight">⚡ 今日矿石已自动累加</span> · 结果实时推送
                </div>
                <div class="separator"></div>
                <div class="footer-text">
                    执行时间 · {current_time}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def main():
    """主函数"""
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

    start_time = format_china_time()
    print(f"[{start_time}] 开始执行掘金签到 (纯Selenium最终版)")

    if not check_config():
        return

    driver = None
    sign_status = "失败"
    sign_detail = "未知错误"
    lottery_info = {
        'type': 'unknown',
        'name': '未执行',
        'value': 0,
        'display': '🎲 未执行'
    }
    user_stats = {'连续签到': '未知', '累计签到': '未知', '矿石总数': '0', '今日获得': '0'}

    try:
        # 启动浏览器
        print("\n🌐 ===== 启动Chrome浏览器 =====")
        driver = setup_driver()
        
        # 添加Cookie
        add_cookies_to_driver(driver, COOKIE)
        
        # 模拟用户行为
        simulate_user_behavior(driver)
        
        # 获取签到前统计数据
        print("\n📊 ===== 获取当前数据 =====")
        user_stats = get_user_stats(driver)
        print(f"当前统计: {user_stats}")
        
        # 初始化今日获得
        today_ore = 0
        
        # 执行签到
        sign_success, sign_result, sign_button, sign_ore = check_and_click_sign(driver)
        
        if sign_success:
            if "已签到" in sign_result:
                sign_status = "已签到"
                sign_detail = "今日已完成签到"
            else:
                sign_status = "签到成功"
                sign_detail = sign_result
                today_ore += sign_ore
                print(f"📝 签到获得 {sign_ore} 矿石")
            
            # 执行抽奖
            lottery_info = check_and_click_lottery(driver)
            
            # 如果是矿石，累加到今日获得
            if lottery_info['type'] == 'ore':
                today_ore += lottery_info['value']
                print(f"📝 抽奖获得 {lottery_info['value']} 矿石")
            
            # 更新今日获得
            user_stats['今日获得'] = str(today_ore)
            print(f"📊 今日共获得 {today_ore} 矿石")
            
            # 重新获取最新数据
            time.sleep(3)
            driver.get(SIGNIN_URL)
            time.sleep(3)
            final_stats = get_user_stats(driver)
            user_stats['连续签到'] = final_stats['连续签到']
            user_stats['累计签到'] = final_stats['累计签到']
            user_stats['矿石总数'] = final_stats['矿石总数']
            
        else:
            sign_status = "签到失败"
            sign_detail = sign_result

    except Exception as e:
        error_msg = str(e)
        print(f"❌ 执行过程中出现异常: {error_msg}")
        sign_detail = f"异常: {error_msg[:100]}"
        
    finally:
        if driver:
            driver.quit()
            print("\n🔚 浏览器已关闭")

        html_content = create_email_html(sign_status, sign_detail, lottery_info, user_stats)
        send_email("掘金签到通知", html_content, is_html=True)

        end_time = format_china_time()
        print(f"[{end_time}] 执行完成")

if __name__ == "__main__":
    main()
