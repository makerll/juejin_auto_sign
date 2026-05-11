#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掘金社区自动签到脚本 - 纯Selenium最终版
全新邮件设计 + 完善的抽奖处理 + Cookie过期通知
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
    """将Cookie字符串解析为Selenium需要的格式 - 不设置domain，避免无效domain错误"""
    cookies = []
    for item in cookie_str.split('; '):
        if '=' in item:
            name, value = item.split('=', 1)
            # 只设置name和value，不设置domain，让浏览器自动处理
            cookies.append({
                'name': name,
                'value': value,
            })
    return cookies

def add_cookies_to_driver(driver, cookie_str):
    """向浏览器添加Cookie - 修复domain问题"""
    print("\n🍪 添加Cookie到浏览器...")
    driver.get(JUEJIN_URL)
    time.sleep(3)
    
    cookies = parse_cookie_string(cookie_str)
    success_count = 0
    failed_count = 0
    
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
            success_count += 1
            print(f"  ✅ 添加cookie: {cookie['name']}")
        except Exception as e:
            failed_count += 1
            print(f"  ❌ 添加cookie {cookie['name']} 失败: {e}")
    
    print(f"✅ 成功添加 {success_count}/{len(cookies)} 个cookie，失败 {failed_count} 个")
    driver.refresh()
    time.sleep(3)
    return success_count > 0

def verify_login(driver):
    """验证是否登录成功"""
    try:
        time.sleep(3)
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        page_title = driver.title
        
        print(f"📄 页面标题: {page_title}")
        print(f"📄 页面文本预览: {page_text[:200]}")
        
        # 检查403错误
        if '403' in page_text or 'denied' in page_text.lower() or 'forbidden' in page_text.lower():
            print("❌ 访问被拒绝，Cookie可能已过期")
            return False, "access_denied"
        
        # 检查是否出现登录相关文字
        if '登录' in page_text and '注册' in page_text:
            print("❌ Cookie无效，页面显示登录界面")
            return False, "login_page"
        
        # 检查是否有用户标识（根据你的用户名）
        if '难为清醒' in page_text:
            print("✅ 登录验证成功")
            return True, "success"
        
        # 检查是否有签到相关元素
        if '签到' in page_text or '矿石' in page_text:
            print("✅ 检测到签到相关元素，登录成功")
            return True, "success"
        
        print("⚠️ 无法确定登录状态，假设成功")
        return True, "assumed_success"
        
    except Exception as e:
        print(f"验证登录状态时出错: {e}")
        return False, f"verification_error:{str(e)}"

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
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    background: #f5f7fa;
                    padding: 20px;
                }}
                .container {{
                    max-width: 500px;
                    margin: 0 auto;
                    background: #ffffff;
                    border-radius: 24px;
                    box-shadow: 0 20px 40px -12px rgba(0, 0, 0, 0.1);
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
                    border-radius: 12px;
                }}
                .message p {{
                    margin: 8px 0;
                    color: #1e293b;
                }}
                .steps {{
                    background: #f8fafc;
                    border-radius: 12px;
                    padding: 16px;
                    margin: 16px 0;
                }}
                .steps ol {{
                    padding-left: 20px;
                    margin: 8px 0;
                }}
                .steps li {{
                    margin: 8px 0;
                    color: #475569;
                }}
                .code {{
                    background: #e2e8f0;
                    padding: 12px;
                    border-radius: 8px;
                    font-family: monospace;
                    font-size: 12px;
                    word-break: break-all;
                    margin: 12px 0;
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
                    </div>
                    
                    <div class="steps">
                        <p><strong>📋 如何更新 Cookie：</strong></p>
                        <ol>
                            <li>打开浏览器无痕模式访问 <a href="https://juejin.cn/">https://juejin.cn/</a></li>
                            <li>登录你的掘金账号</li>
                            <li>按 F12 打开开发者工具 → Network 标签</li>
                            <li>刷新页面，找到任意请求（如 home 或 get_today_status）</li>
                            <li>在请求头中找到 <code>cookie:</code> 字段</li>
                            <li>右键复制完整的 Cookie 值</li>
                            <li>更新 GitHub Secrets 中的 <code>JUEJIN_COOKIE</code></li>
                        </ol>
                    </div>
                    
                    <p class="time">⏱️ 检测时间：{current_time}</p>
                </div>
                <div class="footer">
                    <p>🤖 此邮件由自动签到系统发送</p>
                    <p>请及时更新 Cookie 以恢复自动签到</p>
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

def wait_for_page_load(driver, retry_count=0):
    """等待页面加载，确保数据出现 - 等待非0数字出现"""
    print("\n⏳ 等待页面数据加载...")
    
    # 滚动页面触发加载
    for i in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        print(f"  第{i+1}次滚动")
    
    # 等待数据出现（连续签到天数不为0）
    try:
        print("⏳ 等待用户数据加载（等待非0数字出现）...")
        
        # 等待连续签到天数出现且不为0
        def check_data_loaded(driver):
            try:
                text = driver.find_element(By.TAG_NAME, 'body').text
                # 匹配连续签到天数
                match = re.search(r'(\d+)\s*连续签到天数', text)
                if match and match.group(1) != '0':
                    print(f"✅ 数据加载完成，连续签到: {match.group(1)}")
                    return True
            except:
                pass
            return False
        
        # 最多等待30秒
        WebDriverWait(driver, 30).until(lambda d: check_data_loaded(d))
        
        # 额外等待数据填充
        time.sleep(3)
        
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        numbers = re.findall(r'\b\d+\b', page_text)
        valid_numbers = [n for n in numbers if len(n) >= 3 and not (2020 <= int(n) <= 2030)]
        
        if valid_numbers:
            print(f"✅ 检测到有效数字: {valid_numbers[:3]}")
            return True
        else:
            print("⚠️ 未检测到有效数字")
            
    except TimeoutException:
        print("⚠️ 等待超时，数据仍未加载")
    
    # 如果数据仍未加载，刷新页面重试
    if retry_count < 2:
        print(f"🔄 刷新页面重试 ({retry_count + 1}/2)...")
        driver.refresh()
        time.sleep(5)
        return wait_for_page_load(driver, retry_count + 1)
    
    return False

def get_user_stats(driver):
    """从页面获取用户统计信息 - 加强数据验证"""
    stats = {'连续签到': '未知', '累计签到': '未知', '矿石总数': '0', '今日获得': '0'}

    try:
        # 先等待页面加载
        if not wait_for_page_load(driver):
            print("⚠️ 页面可能未完全加载或数据为空")
        
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        print("📄 页面文本预览:", page_text[:300].replace('\n', ' '))
        
        # 连续签到
        match = re.search(r'(\d+)\s*(?:天)?\s*连续签到天数', page_text)
        if match:
            stats['连续签到'] = match.group(1)
            print(f"📊 连续签到: {stats['连续签到']}")
        
        # 累计签到
        match = re.search(r'(\d+)\s*(?:天)?\s*累计签到天数', page_text)
        if match:
            stats['累计签到'] = match.group(1)
            print(f"📊 累计签到: {stats['累计签到']}")

        # 矿石总数 - 优先使用"当前矿石数"后面的数字
        ore_match = re.search(r'当前矿石数[^\d]*(\d+)', page_text)
        if ore_match:
            stats['矿石总数'] = ore_match.group(1)
            print(f"💰 矿石总数: {stats['矿石总数']}")
        else:
            # 备用方案
            ore_matches = re.findall(r'(\d{4,7})\s*矿石', page_text)
            if ore_matches:
                stats['矿石总数'] = ore_matches[0]
                print(f"💰 矿石总数(备选): {stats['矿石总数']}")
        
        # 如果数据全是0，说明加载失败
        if stats['连续签到'] == '0' and stats['累计签到'] == '0' and stats['矿石总数'] == '0':
            print("⚠️ 警告：所有统计数据均为0，页面可能未正常加载")
            print("💡 提示：掘金页面数据异步加载失败，可能是网络或反爬问题")

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

def create_cookie_expired_html():
    """创建Cookie过期邮件HTML"""
    current_time = format_china_time()
    return f"""
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
            .container {{
                max-width: 500px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 24px;
                box-shadow: 0 20px 40px -12px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #ef4444, #dc2626);
                color: white;
                padding: 24px;
                text-align: center;
            }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 24px; }}
            .warning-icon {{ font-size: 48px; text-align: center; margin-bottom: 20px; }}
            .message {{
                background: #fef2f2;
                border-left: 4px solid #ef4444;
                padding: 16px;
                margin-bottom: 20px;
                border-radius: 12px;
            }}
            .steps {{
                background: #f8fafc;
                border-radius: 12px;
                padding: 16px;
                margin: 16px 0;
            }}
            .steps ol {{ padding-left: 20px; margin: 8px 0; }}
            .steps li {{ margin: 8px 0; color: #475569; }}
            .time {{ color: #64748b; font-size: 14px; text-align: center; margin-top: 20px; }}
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
            <div class="header"><h1>⛏️ 掘金签到</h1></div>
            <div class="content">
                <div class="warning-icon">⚠️</div>
                <div class="message">
                    <p><strong>Cookie 已过期</strong></p>
                    <p>自动签到脚本无法登录掘金，因为存储的 Cookie 已经失效。</p>
                </div>
                <div class="steps">
                    <p><strong>📋 如何更新 Cookie：</strong></p>
                    <ol>
                        <li>打开浏览器无痕模式访问 <a href="https://juejin.cn/">https://juejin.cn/</a></li>
                        <li>登录你的掘金账号</li>
                        <li>按 F12 打开开发者工具 → Network 标签</li>
                        <li>刷新页面，找到任意请求（如 home）</li>
                        <li>在请求头中找到 <code>cookie:</code> 字段</li>
                        <li>右键复制完整的 Cookie 值</li>
                        <li>更新 GitHub Secrets 中的 <code>JUEJIN_COOKIE</code></li>
                    </ol>
                </div>
                <p class="time">⏱️ 检测时间：{current_time}</p>
            </div>
            <div class="footer">
                <p>🤖 此邮件由自动签到系统发送</p>
                <p>请及时更新 Cookie 以恢复自动签到</p>
            </div>
        </div>
    </body>
    </html>
    """

def create_email_html(sign_status, sign_detail, lottery_info, user_stats):
    """创建HTML邮件内容"""
    current_time = format_china_time()

    # 签到状态样式
    if "成功" in sign_status:
        sign_icon = "✅"
        sign_color = "#10b981"
        sign_text = "签到成功"
    elif "已签到" in sign_status:
        sign_icon = "✅"
        sign_color = "#10b981"
        sign_text = "已签到"
    else:
        sign_icon = "⚠️"
        sign_color = "#ef4444"
        sign_text = "签到异常"

    # 抽奖信息
    lottery_display = lottery_info['display']
    
    if lottery_info['type'] == 'ore':
        lottery_icon = "🎁"
        lottery_color = "#8b5cf6"
        lottery_tag = "矿石奖励"
    elif lottery_info['type'] == 'physical':
        lottery_icon = "🎁"
        lottery_color = "#f59e0b"
        lottery_tag = "实物奖品"
    elif lottery_info['type'] == 'none':
        lottery_icon = "🍀"
        lottery_color = "#94a3b8"
        lottery_tag = "未中奖"
    elif lottery_info['type'] == 'already':
        lottery_icon = "⏰"
        lottery_color = "#94a3b8"
        lottery_tag = "今日已抽"
    else:
        lottery_icon = "🎲"
        lottery_color = "#94a3b8"
        lottery_tag = "抽奖完成"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>掘金签到</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', 'Microsoft YaHei', sans-serif;
                background: #f5f7fa;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 16px;
            }}
            .card {{
                max-width: 400px;
                width: 100%;
                background: #ffffff;
                border-radius: 24px;
                box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                padding: 20px 20px 12px;
                border-bottom: 1px solid #f0f2f5;
            }}
            .title-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 4px;
            }}
            .title {{ font-size: 20px; font-weight: 600; color: #3370ff; }}
            .time-badge {{ color: #3370ff; font-size: 13px; background: #f1f5f9; padding: 4px 10px; border-radius: 12px; font-weight: bold; }}
            .date-row {{ color: #94a3b8; font-size: 12px; margin-top: 10px; }}
            .stats-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                padding: 16px 20px;
            }}
            .stat-item {{
                border: 1px solid #f0f2f5;
                background: #fff;
                border-radius: 16px;
                padding: 20px 12px;
                text-align: center;
                box-shadow: 0 4px 12px #ccc;
            }}
            .stat-label {{ font-size: 12px; color: #64748b; margin-bottom: 4px; }}
            .stat-value {{ font-size: 22px; font-weight: 600; color: #0f172a; line-height: 1.2; }}
            .stat-unit {{ font-size: 12px; font-weight: 400; color: #94a3b8; margin-left: 2px; }}
            .results-container {{ display: flex; gap: 12px; padding: 0 20px 20px; }}
            .result-card {{
                flex: 1;
                background: #ffffff;
                border-radius: 16px;
                padding: 16px 12px;
                box-shadow: 0 4px 12px #ccc;
                border: 1px solid #f0f2f5;
            }}
            .card-header {{ display: flex; align-items: center; gap: 6px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px dashed #e9eef2; }}
            .card-header-icon {{ font-size: 18px; }}
            .card-header-title {{ font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px; }}
            .sign-content, .lottery-content {{ display: flex; flex-direction: column; align-items: center; text-align: center; }}
            .sign-icon-large, .lottery-icon-large {{
                width: 48px;
                height: 48px;
                border-radius: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
                margin-bottom: 10px;
            }}
            .sign-icon-large {{ background: {sign_color}10; }}
            .lottery-icon-large {{ background: {lottery_color}10; }}
            .sign-status-text {{ font-size: 16px; font-weight: 600; color: {sign_color}; margin-bottom: 4px; }}
            .sign-detail-text {{ font-size: 12px; color: #64748b; background: #f8fafc; padding: 4px 10px; border-radius: 30px; width: fit-content; margin: 0 auto; }}
            .lottery-prize {{ font-size: 16px; font-weight: 600; color: {lottery_color}; margin-bottom: 4px; }}
            .lottery-type {{ font-size: 12px; color: #64748b; background: #f8fafc; padding: 4px 10px; border-radius: 30px; width: fit-content; margin: 0 auto; }}
            .footer {{ padding: 16px 20px; text-align: center; border-top: 1px solid #f0f2f5; color: #94a3b8; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div class="title-row">
                    <span class="title">⛏️ 掘金签到</span>
                    <span class="time-badge">Selenium</span>
                </div>
                <div class="date-row">⏱️ 执行时间：{current_time}</div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-item"><div class="stat-label">📅 连续签到</div><div class="stat-value">{user_stats['连续签到']}<span class="stat-unit">天</span></div></div>
                <div class="stat-item"><div class="stat-label">📊 累计签到</div><div class="stat-value">{user_stats['累计签到']}<span class="stat-unit">天</span></div></div>
                <div class="stat-item"><div class="stat-label">💎 矿石总数</div><div class="stat-value">{user_stats['矿石总数']}<span class="stat-unit">个</span></div></div>
                <div class="stat-item"><div class="stat-label">✨ 今日获得</div><div class="stat-value">{user_stats['今日获得']}<span class="stat-unit">矿石</span></div></div>
            </div>
            
            <div class="results-container">
                <div class="result-card sign-card">
                    <div class="card-header"><span class="card-header-icon">✍️</span><span class="card-header-title">今日签到</span></div>
                    <div class="sign-content">
                        <div class="sign-icon-large">{sign_icon}</div>
                        <div class="sign-status-text">{sign_text}</div>
                        <div class="sign-detail-text">{sign_detail[:20]}</div>
                    </div>
                </div>
                
                <div class="result-card lottery-card">
                    <div class="card-header"><span class="card-header-icon">🎲</span><span class="card-header-title">幸运抽奖</span></div>
                    <div class="lottery-content">
                        <div class="lottery-icon-large">{lottery_icon}</div>
                        <div class="lottery-prize">{lottery_display[2:] if lottery_display.startswith(('🎁', '🎲', '🍀', '⏰', '❌')) else lottery_display}</div>
                        <div class="lottery-type">{lottery_tag}</div>
                    </div>
                </div>
            </div>
            
            <div class="footer">⚡ 每日自动执行 · 结果实时推送 ⚡</div>
        </div>
    </body>
    </html>
    """
    return html

def main():
    """主函数 - 简化版：直接通过差值计算今日获得"""
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
        
        # ===== 验证登录状态 =====
        login_valid, login_status = verify_login(driver)
        if not login_valid:
            print(f"❌ 登录验证失败: {login_status}")
            # 发送Cookie过期通知邮件
            cookie_expired_html = create_cookie_expired_html()
            send_email("⚠️ 掘金签到 Cookie 已过期", cookie_expired_html, is_html=True)
            sign_detail = f"Cookie已过期: {login_status}"
            raise Exception(f"Cookie invalid: {login_status}")
        # =======================
        
        # 模拟用户行为
        simulate_user_behavior(driver)
        
        # ===== 获取签到前的数据 =====
        print("\n📊 ===== 获取签到前数据 =====")
        before_stats = get_user_stats(driver)
        print(f"签到前统计: {before_stats}")
        
        # 记录签到前的矿石总数
        try:
            before_points = int(before_stats['矿石总数']) if before_stats['矿石总数'] not in ['0', '未知'] else 0
            print(f"💰 签到前矿石总数: {before_points}")
        except:
            before_points = 0
            print("⚠️ 无法解析签到前矿石数")
        
        # 执行签到
        sign_success, sign_result, sign_button, _ = check_and_click_sign(driver)
        
        if sign_success:
            if "已签到" in sign_result:
                sign_status = "已签到"
                sign_detail = "今日已完成签到"
            else:
                sign_status = "签到成功"
                sign_detail = sign_result
            
            # 执行抽奖
            lottery_info = check_and_click_lottery(driver)
            
            # ===== 获取签到+抽奖后的数据 =====
            print("\n📊 ===== 获取最终数据 =====")
            time.sleep(3)
            
            # 返回签到页面
            driver.get(SIGNIN_URL)
            time.sleep(3)
            
            # 滚动触发加载
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            after_stats = get_user_stats(driver)
            print(f"最终统计: {after_stats}")
            
            # 记录签到后的矿石总数
            try:
                after_points = int(after_stats['矿石总数']) if after_stats['矿石总数'] not in ['0', '未知'] else 0
                print(f"💰 签到后矿石总数: {after_points}")
            except:
                after_points = 0
            
            # 通过最终差值计算今日获得的总矿石
            if before_points > 0 and after_points > 0:
                today_ore = after_points - before_points
                print(f"📊 今日共获得矿石: {today_ore}")
            else:
                today_ore = 0
                print("⚠️ 无法通过差值计算今日获得")
            
            # 更新用户统计
            user_stats = {
                '连续签到': after_stats['连续签到'],
                '累计签到': after_stats['累计签到'],
                '矿石总数': after_stats['矿石总数'],
                '今日获得': str(today_ore)
            }
            
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

        # 发送邮件（只有在Cookie有效的情况下才发送正常邮件，否则已发送Cookie过期通知）
        if "Cookie" not in sign_detail:
            html_content = create_email_html(sign_status, sign_detail, lottery_info, user_stats)
            send_email("掘金签到通知", html_content, is_html=True)

        end_time = format_china_time()
        print(f"[{end_time}] 执行完成")
        
if __name__ == "__main__":
    main()
