#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掘金社区自动签到脚本 - Selenium 最终修复版
每天先点击签到，再去抽免费抽奖1次
修复了页面异步加载导致数据读取失败的问题
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
USER_PAGE_URL = "https://juejin.cn/user/center/signin"

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
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
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
    driver.get(JUEJIN_URL)
    time.sleep(2)
    
    cookies = parse_cookie_string(cookie_str)
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print(f"添加cookie {cookie['name']} 失败: {e}")
    
    print(f"已添加 {len(cookies)} 个cookie")
    driver.refresh()
    time.sleep(3)

def wait_for_user_data(driver, timeout=15):
    """等待用户数据加载完成"""
    try:
        print("等待用户数据加载...")
        wait = WebDriverWait(driver, timeout)
        
        # 等待连续签到天数出现且包含数字
        wait.until(lambda d: (
            len(d.find_elements(By.XPATH, '//*[contains(text(), "连续签到天数")]')) > 0 and
            any(char.isdigit() for char in d.find_element(By.TAG_NAME, 'body').text)
        ))
        print("用户数据加载完成")
        return True
    except TimeoutException:
        print("用户数据加载超时")
        return False

def get_user_stats(driver, retry_count=0):
    """获取用户统计信息：连续签到天数、累计签到天数、矿石总数"""
    stats = {'连续签到': '0', '累计签到': '0', '矿石总数': '0', '今日获得': '0'}

    try:
        # 等待数据加载
        wait_for_user_data(driver)
        
        # 获取页面所有可见文本
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        print("====== 页面文本分析 ======")
        print(page_text[:500])
        print("=========================")

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

        # 矿石总数 - 排除年份数字（如2026）
        ore_matches = re.findall(r'(\d{4,7})\s*矿石', page_text)
        if ore_matches:
            stats['矿石总数'] = ore_matches[0]
        else:
            all_numbers = re.findall(r'\b(\d{4,7})\b', page_text)
            # 过滤掉可能的年份（2026-2030）
            valid_ores = [n for n in all_numbers if not (2020 <= int(n) <= 2030)]
            if valid_ores:
                stats['矿石总数'] = max(valid_ores, key=int)
        
        # 数据验证：如果连续签到为0但应该有值，说明页面未加载完整
        if stats['连续签到'] == '0' and '立即签到' in page_text and retry_count < 3:
            print(f"⚠️ 数据异常：连续签到位0，但存在签到按钮，等待后重试 ({retry_count + 1}/3)...")
            time.sleep(3)
            driver.refresh()
            time.sleep(3)
            return get_user_stats(driver, retry_count + 1)

    except Exception as e:
        print(f"获取用户统计信息时出错: {e}")

    return stats

def check_sign_status(driver):
    """检查今日是否已签到，并返回签到按钮"""
    try:
        # 打印页面标题和当前URL用于调试
        print(f"当前页面标题: {driver.title}")
        print(f"当前URL: {driver.current_url}")
        
        # 优先检查是否已显示“今日已签到”状态标签
        signed_elements = driver.find_elements(By.XPATH, '//*[contains(text(), "今日已签到")]')
        for element in signed_elements:
            if element.is_displayed():
                print("检测到'今日已签到'状态标签")
                return True, None

        # 查找可点击的签到按钮
        button_selectors = [
            '//button[contains(text(), "立即签到")]',
            '//button[contains(text(), "签到")]',
            '//div[contains(text(), "立即签到")]',
            '//span[contains(text(), "立即签到")]',
            '//*[contains(@class, "sign") and contains(text(), "签到")]',
            '.signin-btn',
            '.check-in-btn',
            'button.sign-btn',
        ]

        for selector in button_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        tag_name = element.tag_name.lower()
                        print(f"找到可能的签到按钮: 标签={tag_name}, 文本={element.text}, 可见={element.is_displayed()}")
                        return False, element
            except Exception as e:
                continue

        print("未找到明确的签到按钮")
        return True, None

    except Exception as e:
        print(f"检查签到状态时出错: {e}")
        return False, None

def check_sign_success(driver):
    """检查签到是否成功"""
    try:
        # 检查是否出现"今日已签到"
        signed_elements = driver.find_elements(By.XPATH, '//*[contains(text(), "今日已签到")]')
        for element in signed_elements:
            if element.is_displayed():
                print("检测到'今日已签到'标签")
                return True
        
        # 检查签到按钮是否消失或变灰
        buttons = driver.find_elements(By.XPATH, '//button[contains(text(), "立即签到")]')
        if not buttons or not buttons[0].is_displayed():
            print("签到按钮已消失")
            return True
            
        return False
    except:
        return False

def perform_sign(driver, sign_button):
    """执行签到操作 - 改进弹窗检测"""
    try:
        if not sign_button:
            return False, "未找到签到按钮"

        # 滚动到按钮位置
        driver.execute_script("arguments[0].scrollIntoView(true);", sign_button)
        time.sleep(1)

        # 点击签到
        try:
            sign_button.click()
            print("使用常规点击")
        except:
            try:
                driver.execute_script("arguments[0].click();", sign_button)
                print("使用JavaScript点击")
            except:
                actions = ActionChains(driver)
                actions.move_to_element(sign_button).click().perform()
                print("使用ActionChains点击")

        print("已点击签到按钮")
        time.sleep(3)

        # === 检测真正的签到成功弹窗 ===
        reward = "签到成功"
        try:
            # 查找包含"签到成功"或"获得"的弹窗
            popup_elements = driver.find_elements(By.XPATH, 
                '//*[contains(text(), "签到成功") or contains(text(), "获得") and contains(text(), "矿石")]')
            
            for element in popup_elements:
                if element.is_displayed():
                    popup_text = element.text
                    print(f"检测到签到弹窗: {popup_text}")
                    
                    ore_match = re.search(r'(\d+)', popup_text)
                    if ore_match:
                        reward = f"获得 {ore_match.group(1)} 矿石"
                        break
            
            # 尝试关闭弹窗（点击空白处）
            try:
                actions = ActionChains(driver)
                actions.move_by_offset(100, 100).click().perform()
                actions.move_to_element(sign_button).perform()
                print("尝试关闭弹窗")
                time.sleep(1)
            except:
                pass
                
        except Exception as e:
            print(f"弹窗检测跳过: {e}")

        # 验证签到是否成功
        if check_sign_success(driver):
            print("✅ 签到验证成功")
            return True, reward
        else:
            print("⚠️ 签到后状态验证失败，等待2秒重试...")
            time.sleep(2)
            if check_sign_success(driver):
                print("✅ 第二次验证成功")
                return True, reward
            else:
                return False, "签到后状态未改变"

    except Exception as e:
        print(f"执行签到异常: {e}")
        return False, f"签到异常: {str(e)}"

def switch_to_lottery_tab(driver):
    """切换到幸运抽奖菜单"""
    try:
        # 查找并点击"幸运抽奖"标签
        lottery_tab_selectors = [
            '//*[contains(text(), "幸运抽奖")]',
            '//div[@role="tab" and contains(text(), "幸运抽奖")]',
            '.lottery-tab',
            '//*[contains(@class, "tab") and contains(text(), "抽奖")]'
        ]
        
        for selector in lottery_tab_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed():
                        print(f"找到幸运抽奖标签: {element.text}")
                        driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(1)
                        
                        try:
                            element.click()
                        except:
                            driver.execute_script("arguments[0].click();", element)
                        
                        print("已切换到幸运抽奖页面")
                        time.sleep(3)
                        return True
            except:
                continue
        
        print("未找到幸运抽奖标签")
        return False
        
    except Exception as e:
        print(f"切换抽奖标签异常: {e}")
        return False

def check_lottery_available(driver):
    """检查是否有免费抽奖机会，并返回抽奖按钮"""
    try:
        # 先切换到抽奖页面
        if not switch_to_lottery_tab(driver):
            return False, "无法切换到抽奖页面"
        
        # 获取页面文本检查抽奖次数
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        
        # 检查免费抽奖次数
        if '免费抽奖次数：0次' in page_text:
            print("免费抽奖次数已用完")
            return False, "今天已经抽过奖"
        
        if '免费抽奖次数：1次' in page_text:
            print("检测到免费抽奖次数：1次")
        
        # 查找抽奖按钮
        lottery_selectors = [
            '//*[contains(text(), "去抽奖")]',
            '//*[contains(text(), "免费抽奖")]',
            '//button[contains(text(), "抽奖")]',
            '.lottery-btn',
            '.draw-btn',
            '//div[contains(@class, "draw") and contains(@class, "btn")]',
        ]
        
        for selector in lottery_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        print(f"找到抽奖按钮: {element.text}")
                        return True, element
            except:
                continue
        
        # 检查是否已显示抽奖结果
        if '恭喜' in page_text and ('抽中' in page_text or '中奖' in page_text):
            print("检测到已抽过奖的记录")
            return False, "今天已经抽过奖"
        
        return False, "未找到抽奖按钮"
        
    except Exception as e:
        print(f"检查抽奖状态异常: {e}")
        return False, "检查失败"

def perform_lottery(driver, lottery_element):
    """执行抽奖并获取具体奖品信息（包含矿石数量）"""
    try:
        # 滚动到按钮位置
        driver.execute_script("arguments[0].scrollIntoView(true);", lottery_element)
        time.sleep(1)

        # 点击抽奖
        try:
            lottery_element.click()
        except:
            driver.execute_script("arguments[0].click();", lottery_element)

        print("已点击抽奖按钮")
        time.sleep(3)

        # 获取抽奖结果
        page_text = driver.find_element(By.TAG_NAME, 'body').text

        # 匹配带数字的矿石
        ore_match = re.search(r'获得[：:]\s*(\d+)\s*矿石', page_text)
        if ore_match:
            ore_count = ore_match.group(1)
            print(f"🎉 抽中获得 {ore_count} 矿石")
            return f"获得 {ore_count} 矿石"

        ore_match2 = re.search(r'抽中[“”]?(\d+)\s*矿石', page_text)
        if ore_match2:
            ore_count = ore_match2.group(1)
            return f"获得 {ore_count} 矿石"

        # 匹配其他奖品格式
        prize_match = re.search(r'恭喜[^，,\n]+抽中[“”]?([^“”\n]+)[”"]?', page_text)
        if prize_match:
            prize = prize_match.group(1).strip()
            return f"获得: {prize}"

        if '谢谢参与' in page_text:
            return "谢谢参与"

        return "抽奖完成"

    except Exception as e:
        print(f"执行抽奖异常: {e}")
        return f"抽奖异常: {str(e)}"

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
    """创建HTML邮件内容 - 清新优雅紧凑版"""
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
        lottery_badge = "恭喜中奖"
        lottery_color = "#8b5cf6"
    elif "谢谢参与" in lottery_result:
        lottery_icon = "🍀"
        lottery_badge = "谢谢参与"
        lottery_color = "#6b7280"
    elif "已经抽过" in lottery_result:
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
                background: linear-gradient(112deg, #ffffff 0%, #f9fafc 100%);
                border-bottom: 1px solid rgba(0, 0, 0, 0.03);
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
                background: linear-gradient(135deg, #1e293b, #0f172a);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .date-badge {{
                font-size: 13px;
                color: #64748b;
                background: #f1f5f9;
                padding: 4px 10px;
                border-radius: 40px;
            }}
            .sub-title {{
                font-size: 13px;
                color: #64748b;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .dot {{
                width: 4px;
                height: 4px;
                background: #cbd5e1;
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
                    <span>每日自动签到</span>
                    <span class="dot"></span>
                    <span>免费抽奖1次</span>
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
                    ⚡ 每日自动执行 · 结果实时推送 ⚡
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def main():
    """主函数"""
    # ================= 随机等待逻辑 (1-10 分钟) =================
    # 生成 1 到 10 之间的随机整数
    wait_minutes = random.randint(1, 10)
    wait_seconds = wait_minutes * 60
    
    start_time = time.strftime("%H:%M:%S")
    end_time_obj = time.time() + wait_seconds
    end_time_str = time.strftime("%H:%M:%S", time.localtime(end_time_obj))
    
    print(f"🤖 [Juejin Bot] 任务已启动: {start_time}")
    print(f"🎲 [随机策略] 生成随机等待时间: {wait_minutes} 分钟")
    print(f"⏳ [预计执行] 将在约 {end_time_str} 开始签到...")
    print("-" * 30)
    
    # 执行等待
    # 注意：GitHub Actions 日志在 sleep 期间不会更新，这是正常的
    time.sleep(wait_seconds)
    
    print("-" * 30)
    print(f"✅ [唤醒] 等待结束，当前时间: {time.strftime('%H:%M:%S')}")
    print("🚀 开始执行签到逻辑...")
    # =========================================================

    # --- 下面是你原本的签到逻辑 ---
    start_time = format_china_time()
    print(f"[{start_time}] 开始执行掘金签到 (Selenium版)")

    if not check_config():
        return

    driver = None
    sign_status = "失败"
    sign_detail = "未知错误"
    lottery_result = "未执行"
    user_stats = {'连续签到': '0', '累计签到': '0', '矿石总数': '0', '今日获得': '0'}

    try:
        # 随机延迟（5-30秒，模拟人类操作）
        delay = random.randint(5, 30)
        print(f"随机延迟 {delay} 秒")
        time.sleep(delay)

        # 启动浏览器
        print("正在启动Chrome浏览器...")
        driver = setup_driver()

        # 添加Cookie
        print("正在添加Cookie...")
        add_cookies_to_driver(driver, COOKIE)

        # 进入签到页面
        print(f"正在访问签到页面: {USER_PAGE_URL}")
        driver.get(USER_PAGE_URL)
        
        # ===== 等待页面完全加载 =====
        print("等待页面完全加载...")
        time.sleep(5)  # 给初始加载时间
        
        # 滚动页面触发异步加载
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # 等待用户数据加载
        wait_for_user_data(driver)
        # ===========================

        # 获取签到前的初始数据
        print("正在获取签到前用户统计信息...")
        initial_stats = get_user_stats(driver)
        print(f"签到前统计: {initial_stats}")

        # 检查签到状态
        is_signed, sign_button = check_sign_status(driver)
        print(f"今日签到状态: {'已签到' if is_signed else '未签到'}")

        if not is_signed and sign_button:
            # 情况1：未签到 → 先签到，再抽奖
            print("开始执行签到...")
            sign_success, sign_reward = perform_sign(driver, sign_button)

            if sign_success:
                # === 从签到奖励中提取数字 ===
                sign_ore = 0
                if "获得" in sign_reward:
                    reward_numbers = re.findall(r'\d+', sign_reward)
                    if reward_numbers:
                        sign_ore = int(reward_numbers[0])
                        user_stats['今日获得'] = str(sign_ore)
                        print(f"今日签到获得: {sign_ore} 矿石")
                else:
                    # 如果没提取到，通过页面中的+号提取
                    time.sleep(1)
                    page_text = driver.find_element(By.TAG_NAME, 'body').text
                    plus_matches = re.findall(r'\+(\d+)', page_text)
                    if plus_matches:
                        sign_ore = int(plus_matches[0])
                        user_stats['今日获得'] = str(sign_ore)
                        print(f"今日签到获得(从+号提取): {sign_ore} 矿石")

                sign_status = "签到成功"
                sign_detail = sign_reward
                print(f"✅ {sign_status}: {sign_detail}")

                # 验证数据是否真的变化
                time.sleep(2)
                verify_stats = get_user_stats(driver)
                print(f"签到后验证统计: {verify_stats}")

                # 签到成功 → 去抽奖
                print("\n=== 签到完成，开始执行抽奖 ===")
                lottery_available, lottery_element = check_lottery_available(driver)

                if lottery_available and lottery_element:
                    print("发现免费抽奖机会，开始抽奖...")
                    lottery_result = perform_lottery(driver, lottery_element)
                    
                    # 如果是矿石，累加到今日获得
                    if "矿石" in lottery_result:
                        ore_match = re.search(r'(\d+)', lottery_result)
                        if ore_match:
                            lottery_ore = int(ore_match.group(1))
                            current_total = int(user_stats['今日获得'] or 0)
                            user_stats['今日获得'] = str(current_total + lottery_ore)
                            print(f"今日抽奖获得: {lottery_ore} 矿石，累计: {user_stats['今日获得']}")
                else:
                    lottery_result = lottery_element if isinstance(lottery_element, str) else "今天已经抽过奖"
                    print(f"抽奖状态: {lottery_result}")
            else:
                sign_status = "签到失败"
                sign_detail = sign_reward
                print(f"❌ {sign_status}")
                lottery_result = "签到失败，未抽奖"

        else:
            # 情况2：已签到 → 只抽奖
            sign_status = "已签到"
            sign_detail = "今日已完成签到"
            print(f"✅ {sign_status}")
            
            print("\n=== 今日已签到，检查抽奖机会 ===")
            lottery_available, lottery_element = check_lottery_available(driver)

            if lottery_available and lottery_element:
                print("发现免费抽奖机会，开始抽奖...")
                lottery_result = perform_lottery(driver, lottery_element)
                
                if "矿石" in lottery_result:
                    ore_match = re.search(r'(\d+)', lottery_result)
                    if ore_match:
                        lottery_ore = int(ore_match.group(1))
                        user_stats['今日获得'] = str(lottery_ore)
                        print(f"今日抽奖获得: {lottery_ore} 矿石")
            else:
                lottery_result = lottery_element if isinstance(lottery_element, str) else "今天已经抽过奖"
                print(f"抽奖状态: {lottery_result}")

        # === 在所有操作完成后，重新获取最新的统计数据 ===
        print("\n=== 操作完成，获取最新统计数据 ===")
        time.sleep(3)
        
        # 切换回签到页面
        print("正在切换回签到页面...")
        driver.get(USER_PAGE_URL)
        time.sleep(3)
        
        # 重新获取最新数据
        final_stats = get_user_stats(driver)
        print(f"最终统计: {final_stats}")
        
        # 更新 user_stats 为最终数据
        user_stats['连续签到'] = final_stats['连续签到']
        user_stats['累计签到'] = final_stats['累计签到']
        user_stats['矿石总数'] = final_stats['矿石总数']
        # 今日获得已经在过程中累加，保持不变

        print(f"\n最终结果 - 签到: {sign_status}, 抽奖: {lottery_result}")

    except Exception as e:
        error_msg = str(e)
        print(f"执行过程中出现异常: {error_msg}")
        sign_detail = f"异常: {error_msg[:100]}"
        if driver:
            try:
                driver.save_screenshot("error.png")
                print("已保存错误截图")
            except:
                pass

    finally:
        # 关闭浏览器
        if driver:
            driver.quit()
            print("浏览器已关闭")

        # 发送邮件
        html_content = create_email_html(sign_status, sign_detail, lottery_result, user_stats)
        send_email("掘金签到通知", html_content, is_html=True)

        end_time = format_china_time()
        print(f"[{end_time}] 执行完成")

if __name__ == "__main__":
    main()

