import sys
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright

def get_chrome_path():
    """
    针对 Windows 系统自动探测 Chrome 安装位置
    """
    potential_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in potential_paths:
        if os.path.exists(path):
            return path
    return None

def run_spider():
    # 路径处理
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    auth_file = os.path.join(base_path, "1688_auth.json")
    output_name = os.path.join(base_path, "1688抓取清单.xlsx")
    data = []

    with sync_playwright() as p:
        # 获取本地 Chrome 路径
        local_chrome = get_chrome_path()
        
        if local_chrome:
            print(f"✅ 成功定位本地 Chrome: {local_chrome}")
            # 使用 executable_path 参数启动本地浏览器
            browser = p.chromium.launch(executable_path=local_chrome, headless=False, slow_mo=500)
        else:
            print("❌ 未在默认路径找到 Chrome，尝试使用 Playwright 默认模式启动...")
            browser = p.chromium.launch(headless=False, slow_mo=500)

        # 加载凭证并抹除特征
        context = browser.new_context(storage_state=auth_file if os.path.exists(auth_file) else None)
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        try:
            # 1. 访问并搜索
            page.goto("https://www.1688.com")
            
            # 简单判断是否登录成功，没成功就停一下
            if not os.path.exists(auth_file):
                input("👉 请先完成登录，登录后在终端按【回车】...")
                context.storage_state(path=auth_file)

            print("\n🔍 正在搜索关键词...")
            page.fill("#alisearch-input", "手套")
            page.keyboard.press("Enter")

            # 2. 【核心拦截】给验证码留足时间
            print("⏳ 观察浏览器：如果出现滑块，请滑动。")
            print("💡 注意：滑完之后，如果页面没动，请在终端按回车。")
            input("👉 滑块验证通过并看到商品列表后，请回来按【回车】继续抓取...")

            # 3. 如果页面卡在验证页，手动强制刷一次结果页
            # 有时候滑完不跳转是 1688 的防爬手段
            if "nocaptcha" in page.url or "captcha" in page.url:
                print("检测到页面未自动跳转，正在强制重定向到搜索页...")
                page.goto("https://s.1688.com/selloffer/offer_search.htm?keywords=手套")
                time.sleep(3)

            # 4. 再次确认页面内容
            page.wait_for_load_state("networkidle")
            
            # 5. 扫描商品
            # 我们用最原始的标签定位：找所有 a 标签里包含 title 属性的
            # 或者是尝试寻找常见的价格符号 '¥'
            print("🚀 正在扫描页面元素...")
            
            # 滚动一下
            page.mouse.wheel(0, 1000)
            time.sleep(2)

            # 尝试定位商品卡片
            # 现在的 1688 可能会把商品包在 'search-offer-item' 或是特殊的 div 里
            items = page.locator("//div[contains(@class, 'offer') or contains(@class, 'item')]")
            
            count = 0
            # 真正的查账：遍历所有可能的 div，过滤出有标题的
            all_divs = page.locator("div[class*='offer']").all()
            for div in all_divs:
                try:
                    title_node = div.locator("[class*='title']").first
                    price_node = div.locator("[class*='price']").first
                    
                    if title_node.is_visible() and price_node.is_visible():
                        t_text = title_node.inner_text().strip()
                        p_text = price_node.inner_text().strip()
                        if t_text and p_text:
                            data.append({"商品标题": t_text, " ": "", "参考价格": p_text})
                            count += 1
                except:
                    continue
                if count >= 20: break

            print(f"📊 最终抓取到 {len(data)} 条数据")

        except Exception as e:
            print(f"❌ 出错: {e}")
        finally:
            if not data:
                print("💡 因为没抓到数据，我特意没关浏览器，你可以去浏览器里点点看是怎么回事。")
                input("👉 检查完后，按回车关闭浏览器并结束程序...")
            
            context.close()
            browser.close()

    if data:
        pd.DataFrame(data).to_excel(output_name, index=False)
        print(f"✅ 完成！保存在: {output_name}")

if __name__ == "__main__":
    run_spider()