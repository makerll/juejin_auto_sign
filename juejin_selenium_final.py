#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掘金社区自动签到脚本 - 纯Selenium最终版
完全依赖浏览器自动处理会话、Cookie和CSRF令牌
针对GitHub Actions环境优化
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
LOTTERY_URL = "https://juejin.cn/user/center/lottery"

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
    """配置Chrome浏览器选项 - 针对GitHub Actions优化"""
    chrome_options = Options()
    
    # 无头模式 - 必须的
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # 反检测设置
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')
    
    # 禁用自动化控制标志
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 禁用图片加载，加快速度
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)
    
    # 增加稳定性选项
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-dev-tools')
    chrome_options.add_argument('--no-zygote')
    chrome_options.add_argument('--single-process')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--log-level=3')  # 减少日志

    # 使用 webdriver-manager 自动管理 ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # 隐藏 webdriver 属性
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # 设置页面加载超时
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
    
    # 先访问一次首页建立会话
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
    
    # 刷新页面使Cookie生效
    driver.refresh()
    time.sleep(3)
    return success_count > 0

def safe_find_element(driver, by, selector, timeout=10):
    """安全查找元素，带超时"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return element
    except:
        return None

def safe_click(driver, element, description="元素"):
    """安全点击元素，多种尝试"""
    try:
        # 滚动到元素位置
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(1)
        
        # 尝试常规点击
        try:
            element.click()
            print(f"✅ 点击{description}成功（常规点击）")
            return True
        except:
            # 尝试JavaScript点击
            try:
                driver.execute_script("arguments[0].click();", element)
                print(f"✅ 点击{description}成功（JavaScript点击）")
                return True
            except:
                # 尝试ActionChains点击
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
        # 1. 访问首页
        print("📱 步骤1: 访问掘金首页...")
        driver.get(HOME_URL)
        time.sleep(random.uniform(2, 4))
        print(f"   页面标题: {driver.title}")
        
        # 随机滚动
        scroll_height = random.randint(300, 800)
        driver.execute_script(f"window.scrollTo(0, {scroll_height});")
        print(f"   📜 向下滚动 {scroll_height}px")
        time.sleep(random.uniform(1, 3))
        
        # 2. 访问沸点页面
        print("\n💬 步骤2: 访问沸点页面...")
        driver.get(PIN_URL)
        time.sleep(random.uniform(2, 4))
        
        # 随机滚动
        scroll_height = random.randint(300, 800)
        driver.execute_script(f"window.scrollTo(0, {scroll_height});")
        print(f"   📜 向下滚动 {scroll_height}px")
        time.sleep(random.uniform(1, 3))
        
        # 3. 返回签到页面
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
        # 获取页面所有可见文本
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
        # 先检查是否已签到
        signed_elements = driver.find_elements(By.XPATH, '//*[contains(text(), "今日已签到")]')
        for element in signed_elements:
            if element.is_displayed():
                print("✅ 今日已签到")
                return True, "已签到", None
        
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
                        
                        # 点击签到
                        if safe_click(driver, element, "签到按钮"):
                            print("⏳ 等待签到结果...")
                            time.sleep(5)
                            
                            # 检查是否出现成功弹窗
                            try:
                                popup = driver.find_element(By.XPATH, '//*[contains(text(), "签到成功") or contains(text(), "获得")]')
                                if popup.is_displayed():
                                    popup_text = popup.text
                                    print(f"🎉 签到成功弹窗: {popup_text}")
                                    
                                    # 提取奖励数字
                                    ore_match = re.search(r'(\d+)', popup_text)
                                    if ore_match:
                                        reward = f"获得 {ore_match.group(1)} 矿石"
                                    else:
                                        reward = "签到成功"
                                    
                                    return True, reward, element
                            except:
                                pass
                            
                            return True, "签到成功", element
            except:
                continue
        
        print("❌ 未找到签到按钮")
        return False, "未找到签到按钮", None
        
    except Exception as e:
        print(f"❌ 检查签到状态时出错: {e}")
        return False, f"错误: {str(e)}", None

def check_and_click_lottery(driver):
    """检查并点击抽奖"""
    print("\n🎲 检查抽奖机会...")
    
    try:
        # 先尝试切换到抽奖页面
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
                        
                        # 点击抽奖
                        if safe_click(driver, element, "抽奖按钮"):
                            print("⏳ 等待抽奖结果...")
                            time.sleep(5)
                            
                            # 获取抽奖结果
                            page_text = driver.find_element(By.TAG_NAME, 'body').text
                            
                            # 尝试提取奖品
                            prize_match = re.search(r'获得[：:]\s*([^\n，。,.]+)', page_text)
                            if prize_match:
                                prize = prize_match.group(1).strip()
                                print(f"🎉 抽奖获得: {prize}")
                                return prize
                            
                            # 常见奖品
                            common_prizes = ['矿石', '盲盒', '小夜灯', '耳机', '兑换券']
                            for prize in common_prizes:
                                if prize in page_text:
                                    print(f"🎉 抽奖获得: {prize}")
                                    return prize
                            
                            return "抽奖完成"
            except:
                continue
        
        print("⏰ 未找到抽奖按钮，可能今天已抽过")
        return "今天已经抽过奖"
        
    except Exception as e:
        print(f"❌ 抽奖过程出错: {e}")
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
    if "获得" in lottery_result:
        lottery_icon = "🎁"
        lottery_color = "#8b5cf6"
    elif "今天已经抽过" in lottery_result:
        lottery_icon = "⏰"
        lottery_color = "#f59e0b"
    else:
        lottery_icon = "❓"
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
            .footer {{
                padding: 16px 24px 20px;
                text-align: center;
                border-top: 1px solid #f1f5f9;
                background: #ffffff;
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
                    <span>纯Selenium模式</span>
                    <span class="dot"></span>
                    <span>完全模拟浏览器</span>
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
                    </div>
                    <div class="lottery-content">
                        <div class="lottery-icon" style="background: {lottery_color}15;">{lottery_icon}</div>
                        <div class="lottery-info">
                            <div class="lottery-result">{lottery_result}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <div class="footer-text">
                    ⚡ 纯Selenium · 自动处理会话 ⚡
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
    print(f"[{start_time}] 开始执行掘金签到 (纯Selenium最终版)")

    if not check_config():
        return

    driver = None
    sign_status = "失败"
    sign_detail = "未知错误"
    lottery_result = "未执行"
    user_stats = {'连续签到': '未知', '累计签到': '未知', '矿石总数': '0', '今日获得': '0'}

    try:
        # 启动浏览器
        print("\n🌐 ===== 启动Chrome浏览器 =====")
        driver = setup_driver()
        
        # 添加Cookie
        add_cookies_to_driver(driver, COOKIE)
        
        # 模拟用户行为（访问首页、沸点）
        simulate_user_behavior(driver)
        
        # 获取签到前统计数据
        print("\n📊 ===== 获取当前数据 =====")
        user_stats = get_user_stats(driver)
        print(f"当前统计: {user_stats}")
        
        # 执行签到
        sign_success, sign_result, sign_button = check_and_click_sign(driver)
        
        if sign_success:
            if "已签到" in sign_result:
                sign_status = "已签到"
                sign_detail = "今日已完成签到"
            else:
                sign_status = "签到成功"
                sign_detail = sign_result
                
                # 提取奖励数字
                ore_match = re.search(r'(\d+)', sign_result)
                if ore_match:
                    user_stats['今日获得'] = ore_match.group(1)
            
            # 执行抽奖
            lottery_result = check_and_click_lottery(driver)
            
            # 如果是矿石，累加到今日获得
            if "矿石" in lottery_result and "获得" in lottery_result:
                ore_match = re.search(r'(\d+)', lottery_result)
                if ore_match:
                    lottery_ore = ore_match.group(1)
                    current_total = int(user_stats['今日获得'] or 0)
                    user_stats['今日获得'] = str(current_total + int(lottery_ore))
            
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
        # 关闭浏览器
        if driver:
            driver.quit()
            print("\n🔚 浏览器已关闭")

        # 发送邮件
        html_content = create_email_html(sign_status, sign_detail, lottery_result, user_stats)
        send_email("掘金签到通知 - 纯Selenium版", html_content, is_html=True)

        end_time = format_china_time()
        print(f"[{end_time}] 执行完成")

if __name__ == "__main__":
    main()
