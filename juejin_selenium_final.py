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


def wait_for_page_load(driver, retry_count=0):
    """等待页面加载，确保数据出现"""
    print("\n⏳ 等待页面数据加载...")

    # 滚动页面触发加载
    for i in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        print(f"  第{i + 1}次滚动")

    # 等待关键元素出现
    try:
        # 等待连续签到天数出现
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "连续签到天数")]'))
        )
        print("✅ 检测到连续签到天数元素")

        # 额外等待数据填充
        time.sleep(3)

        # 检查是否有有效数据
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        numbers = re.findall(r'\b\d+\b', page_text)
        valid_numbers = [n for n in numbers if len(n) >= 3 and not (2020 <= int(n) <= 2030)]

        if valid_numbers:
            print(f"✅ 检测到有效数字: {valid_numbers[:3]}")
            return True
        else:
            print("⚠️ 未检测到有效数字")

    except TimeoutException:
        print("⚠️ 等待超时")

    # 如果数据仍未加载，刷新页面重试
    if retry_count < 2:
        print(f"🔄 刷新页面重试 ({retry_count + 1}/2)...")
        driver.refresh()
        time.sleep(5)
        return wait_for_page_load(driver, retry_count + 1)

    return False


def get_user_stats(driver):
    """从页面获取用户统计信息"""
    stats = {'连续签到': '未知', '累计签到': '未知', '矿石总数': '0', '今日获得': '0'}

    try:
        # 先等待页面加载
        if not wait_for_page_load(driver):
            print("⚠️ 页面可能未完全加载")

        page_text = driver.find_element(By.TAG_NAME, 'body').text
        print("📄 页面文本预览:", page_text[:300].replace('\n', ' '))

        # 连续签到
        match = re.search(r'(\d+)\s*(?:天)?\s*连续签到天数', page_text)
        if not match:
            match = re.search(r'(\d+)[^\d]*连续', page_text)
        if match:
            stats['连续签到'] = match.group(1)
            print(f"📊 连续签到: {stats['连续签到']}")

        # 累计签到
        match = re.search(r'(\d+)\s*(?:天)?\s*累计签到天数', page_text)
        if not match:
            match = re.search(r'(\d+)[^\d]*累计', page_text)
        if match:
            stats['累计签到'] = match.group(1)
            print(f"📊 累计签到: {stats['累计签到']}")

        # 矿石总数
        ore_matches = re.findall(r'(\d{4,7})\s*矿石', page_text)
        if ore_matches:
            stats['矿石总数'] = ore_matches[0]
            print(f"💰 矿石总数: {stats['矿石总数']}")
        else:
            all_numbers = re.findall(r'\b(\d{4,7})\b', page_text)
            valid_ores = [n for n in all_numbers if not (2020 <= int(n) <= 2030)]
            if valid_ores:
                stats['矿石总数'] = max(valid_ores, key=int)
                print(f"💰 矿石总数(推断): {stats['矿石总数']}")

    except Exception as e:
        print(f"获取用户统计信息时出错: {e}")

    return stats


def verify_login(driver):
    """验证是否已成功登录"""
    print("\n🔐 验证登录状态...")
    try:
        # 等待页面加载完成
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)

        # 检查是否存在用户头像或用户中心入口（已登录标志）
        logged_in_selectors = [
            '.user-avatar',
            '.sidebar-avatar',
            '[class*="avatar"]',
            '//a[contains(@href, "/user/")]',
        ]
        for selector in logged_in_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        print("✅ 登录状态验证通过")
                        return True
            except:
                continue

        # 备选：检查cookie中是否有sessionid
        cookies = driver.get_cookies()
        session_cookies = [c for c in cookies if c['name'] in ('sessionid', 'sessionid_ss', 'passport_csrf_token')]
        if session_cookies:
            print("✅ 检测到有效session cookie")
            return True

        print("❌ 登录状态验证失败，可能cookie已失效")
        return False
    except Exception as e:
        print(f"❌ 验证登录状态时出错: {e}")
        return False


def dismiss_popups(driver):
    """关闭可能的弹窗/遮罩层"""
    print("\n🔕 检查并关闭弹窗...")
    dismiss_selectors = [
        '//div[contains(@class, "close")]',
        '//button[contains(@class, "close")]',
        '//div[contains(@class, "modal")]//button',
        '//span[contains(@class, "close")]',
        '.dy-dialog-close',
        '.close-btn',
    ]
    dismissed = 0
    for selector in dismiss_selectors:
        try:
            if selector.startswith('//'):
                elements = driver.find_elements(By.XPATH, selector)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    el.click()
                    dismissed += 1
                    time.sleep(0.5)
        except:
            continue
    if dismissed:
        print(f"✅ 关闭了 {dismissed} 个弹窗")
    else:
        print("✅ 无弹窗")
    time.sleep(1)


def find_sign_button(driver):
    """查找签到按钮，使用WebDriverWait等待"""
    button_selectors = [
        (By.XPATH, '//button[contains(text(), "立即签到")]'),
        (By.XPATH, '//button[contains(text(), "签到")]'),
        (By.XPATH, '//div[contains(text(), "立即签到")]'),
        (By.CSS_SELECTOR, '.signin-btn'),
        (By.CSS_SELECTOR, '.check-in-btn'),
    ]

    for by, selector in button_selectors:
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((by, selector))
            )
            elements = driver.find_elements(by, selector)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    print(f"✅ 找到签到按钮: {element.text}")
                    return element
        except TimeoutException:
            continue
        except Exception:
            continue
    return None


def check_and_click_sign(driver):
    """检查并点击签到按钮（含重试机制）"""
    print("\n🔍 检查签到状态...")

    max_retries = 3

    for attempt in range(1, max_retries + 1):
        print(f"\n🔄 签到尝试 ({attempt}/{max_retries})...")

        try:
            # 先关闭可能的弹窗
            dismiss_popups(driver)

            # 检查是否已签到
            signed_elements = driver.find_elements(By.XPATH, '//*[contains(text(), "今日已签到")]')
            for element in signed_elements:
                if element.is_displayed():
                    print("✅ 今日已签到")
                    return True, "已签到", None, 0

            # 等待并查找签到按钮
            sign_button = find_sign_button(driver)
            if sign_button is None:
                print(f"⚠️ 第{attempt}次未找到签到按钮")
                if attempt < max_retries:
                    driver.refresh()
                    time.sleep(5)
                    continue
                return False, "未找到签到按钮", None, 0

            # 点击签到
            if safe_click(driver, sign_button, "签到按钮"):
                print("⏳ 等待签到结果...")
                time.sleep(5)

                # 检查是否变成"已签到"状态（更可靠的判断）
                time.sleep(2)
                signed_after = driver.find_elements(By.XPATH, '//*[contains(text(), "今日已签到")]')
                for el in signed_after:
                    if el.is_displayed():
                        print("✅ 签到成功（状态已变更为已签到）")
                        return True, "签到成功", sign_button, 0

                # 检查弹窗并提取奖励
                try:
                    popup = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.XPATH, '//*[contains(text(), "签到成功") or contains(text(), "获得")]')
                        )
                    )
                    if popup.is_displayed():
                        popup_text = popup.text
                        print(f"🎉 签到成功弹窗: {popup_text}")
                        ore_match = re.search(r'(\d+)', popup_text)
                        if ore_match:
                            ore_count = int(ore_match.group(1))
                            reward = f"获得 {ore_count} 矿石"
                            return True, reward, sign_button, ore_count
                except:
                    pass

                # 点击成功但未检测到明确结果，视为成功
                return True, "签到成功", sign_button, 0
            else:
                print(f"⚠️ 第{attempt}次点击签到按钮失败")
                if attempt < max_retries:
                    driver.refresh()
                    time.sleep(5)

        except Exception as e:
            print(f"⚠️ 第{attempt}次签到出错: {e}")
            if attempt < max_retries:
                driver.refresh()
                time.sleep(5)

    print("❌ 签到失败，已达最大重试次数")
    return False, "未找到签到按钮", None, 0


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


def send_email(subject, content, is_html=False, max_retries=3):
    """发送邮件通知（含重试机制）"""
    if not all([EMAIL_FROM, EMAIL_PASSWORD, SMTP_SERVER]):
        print("邮件配置不完整，跳过邮件发送")
        return False

    for attempt in range(1, max_retries + 1):
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
            print(f"✅ 邮件发送成功")
            return True
        except Exception as e:
            print(f"❌ 邮件发送失败 (第{attempt}/{max_retries}次): {e}")
            if attempt < max_retries:
                wait = attempt * 5
                print(f"⏳ {wait}秒后重试...")
                time.sleep(wait)

    print("❌ 邮件发送最终失败，已达最大重试次数")
    return False


def get_failure_tips(sign_detail):
    """根据失败原因生成排查建议"""
    tips = []
    detail_lower = sign_detail.lower() if sign_detail else ""

    if "cookie" in detail_lower or "登录" in detail_lower or "login" in detail_lower:
        tips.append("Cookie 可能已过期，请重新登录掘金获取最新 Cookie")
        tips.append("检查 Cookie 是否包含 sessionid 和 sessionid_ss 字段")
    elif "按钮" in detail_lower or "元素" in detail_lower:
        tips.append("掘金页面结构可能已更新，请检查签到按钮选择器")
        tips.append("网络延迟导致页面未完全加载，可稍后重试")
    elif "超时" in detail_lower or "timeout" in detail_lower:
        tips.append("网络连接不稳定，请检查服务器网络状况")
        tips.append("掘金服务器可能暂时不可用")
    elif "异常" in detail_lower or "error" in detail_lower or "错误" in detail_lower:
        tips.append("脚本运行出现异常，请检查日志排查具体原因")
        tips.append("可能是 Chrome 浏览器或 ChromeDriver 版本不匹配")
    else:
        tips.append("请检查服务器网络连接是否正常")
        tips.append("确认掘金 Cookie 是否仍然有效")

    tips.append("如问题持续，请手动登录掘金确认账号状态")
    return tips


def create_email_html(sign_status, sign_detail, lottery_info, user_stats):
    """创建HTML邮件内容"""
    current_time = format_china_time()

    is_failure = "失败" in sign_status or "异常" in sign_status

    # 签到状态
    if "成功" in sign_status:
        sign_text = "签到成功"
    elif "已签到" in sign_status:
        sign_text = "已签到"
    else:
        sign_text = "签到失败"

    # 状态色
    status_color = "#22c55e" if not is_failure else "#ef4444"

    # 抽奖显示文本（去掉前缀emoji）
    lottery_display = lottery_info['display']
    lottery_raw = lottery_display[2:] if lottery_display.startswith(('🎁', '🎲', '🍀', '⏰', '❌', '⏸️')) else lottery_display

    # 失败排查建议
    failure_block = ""
    if is_failure:
        tips = get_failure_tips(sign_detail)
        tips_html = "".join(f'<div style="margin-top:4px;">- {tip}</div>' for tip in tips)
        failure_block = f"""
        <tr>
            <td style="padding:16px 24px;border-bottom:1px solid #f0f0f0;background:#fafafa;">
                <div style="font-size:12px;font-weight:600;color:#c00;margin-bottom:6px;">排查建议</div>
                <div style="font-size:12px;color:#666;line-height:1.8;">{tips_html}</div>
            </td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>掘金签到</title></head>
    <body style="margin:0;padding:0;background:#f4f4f4;font-family:'Helvetica Neue',Helvetica,'Microsoft YaHei',Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:24px 0;">
            <tr><td align="center">
                <table width="380" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

                    <!-- 顶部装饰线 -->
                    <tr><td style="height:3px;background:linear-gradient(90deg, #1e80ff, #46a3ff);"></td></tr>

                    <!-- 标题栏 -->
                    <tr>
                        <td style="padding:20px 24px 16px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size:16px;font-weight:600;color:#1a1a1a;">掘金签到</td>
                                    <td align="right" style="font-size:12px;color:#999;">{current_time}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- 签到状态 -->
                    <tr>
                        <td style="padding:16px 24px;border-top:1px solid #f0f0f0;border-bottom:1px solid #f0f0f0;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size:13px;color:#666;">签到状态</td>
                                    <td align="right">
                                        <span style="display:inline-block;padding:3px 10px;background:{status_color}15;color:{status_color};font-size:12px;font-weight:500;border-radius:12px;">{sign_text}</span>
                                    </td>
                                </tr>
                            </table>
                            <div style="font-size:12px;color:#999;margin-top:8px;">{sign_detail}</div>
                        </td>
                    </tr>

                    <!-- 幸运抽奖 -->
                    <tr>
                        <td style="padding:16px 24px;border-bottom:1px solid #f0f0f0;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size:13px;color:#666;">幸运抽奖</td>
                                    <td align="right" style="font-size:13px;color:#333;font-weight:500;">{lottery_raw}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- 数据概览 -->
                    <tr>
                        <td style="padding:16px 24px;background:#fafbfc;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td width="50%" style="padding:8px 12px;background:#fff;border-radius:6px;border:1px solid #f0f0f0;">
                                        <div style="font-size:11px;color:#999;">连续签到</div>
                                        <div style="font-size:18px;font-weight:600;color:#1a1a1a;margin-top:4px;">{user_stats['连续签到']} <span style="font-size:11px;font-weight:400;color:#999;">天</span></div>
                                    </td>
                                    <td width="50%" style="padding:8px 12px;background:#fff;border-radius:6px;border:1px solid #f0f0f0;">
                                        <div style="font-size:11px;color:#999;">累计签到</div>
                                        <div style="font-size:18px;font-weight:600;color:#1a1a1a;margin-top:4px;">{user_stats['累计签到']} <span style="font-size:11px;font-weight:400;color:#999;">天</span></div>
                                    </td>
                                </tr>
                                <tr>
                                    <td width="50%" style="padding:8px 12px;margin-top:8px;background:#fff;border-radius:6px;border:1px solid #f0f0f0;">
                                        <div style="font-size:11px;color:#999;">矿石总数</div>
                                        <div style="font-size:18px;font-weight:600;color:#1a1a1a;margin-top:4px;">{user_stats['矿石总数']}</div>
                                    </td>
                                    <td width="50%" style="padding:8px 12px;margin-top:8px;background:#fff;border-radius:6px;border:1px solid #f0f0f0;">
                                        <div style="font-size:11px;color:#999;">今日获得</div>
                                        <div style="font-size:18px;font-weight:600;color:#1e80ff;margin-top:4px;">{user_stats['今日获得']} <span style="font-size:11px;font-weight:400;color:#999;">矿石</span></div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    {failure_block}

                    <!-- 底部 -->
                    <tr>
                        <td style="padding:16px 24px;text-align:center;border-top:1px solid #f0f0f0;">
                            <span style="font-size:11px;color:#bbb;">自动签到 · 每日执行</span>
                        </td>
                    </tr>

                </table>
            </td></tr>
        </table>
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

        # 验证登录状态
        if not verify_login(driver):
            print("❌ 登录验证失败，尝试继续执行...")
            sign_status = "签到失败"
            sign_detail = "登录验证失败，cookie可能已失效"
            # 不直接return，仍尝试继续，因为验证可能误判
            # 但如果真的未登录，后续签到也会失败并被重试机制捕获

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
        sign_status = "签到失败"
        sign_detail = f"异常: {error_msg[:100]}"

    finally:
        if driver:
            driver.quit()
            print("\n🔚 浏览器已关闭")

        # 发送邮件（标题根据签到结果动态变化）
        html_content = create_email_html(sign_status, sign_detail, lottery_info, user_stats)
        current_date = format_china_time()[:10]
        if "成功" in sign_status:
            email_subject = f"掘金签到成功 ({current_date})"
        elif "已签到" in sign_status:
            email_subject = f"掘金已签到 ({current_date})"
        else:
            email_subject = f"掘金签到失败 ({current_date})"
        send_email(email_subject, html_content, is_html=True)

        end_time = format_china_time()
        print(f"[{end_time}] 执行完成")


if __name__ == "__main__":
    main()



