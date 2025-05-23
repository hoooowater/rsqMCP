# -*- coding: utf-8 -*-
from typing import Any, List, Dict, Optional
import asyncio
import json
import os
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright
from fastmcp import FastMCP

# 初始化 MCP 服务
mcp = FastMCP("imooc_course_scraper")

# 全局变量
BROWSER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_data")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 浏览器上下文共享
browser_context = None
main_page = None
is_logged_in = False


async def ensure_browser():
    """确保浏览器已启动并登录"""
    global browser_context, main_page, is_logged_in

    if browser_context is None:
        pw = await async_playwright().start()
        browser_context = await pw.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            timeout=60000
        )
        # 创建主页标签页
        if browser_context.pages:
            main_page = browser_context.pages[0]
        else:
            main_page = await browser_context.new_page()

        main_page.set_default_timeout(60000)

    if not is_logged_in:
        await main_page.goto("https://www.imooc.com", timeout=60000)
        await main_page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # 检查是否存在用户头像或用户信息元素
        user_info = await main_page.query_selector('.user-card-box')
        if user_info:
            is_logged_in = True
            return True
        return False
    return True


@mcp.tool()
async def login() -> str:
    """登录慕课网账号"""
    global is_logged_in
    await ensure_browser()

    if is_logged_in:
        return "已登录慕课网账号"

    await main_page.goto("https://www.imooc.com", timeout=60000)
    await main_page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    # 检查是否需要登录
    user_info = await main_page.query_selector('.user-card-box')
    if user_info:
        is_logged_in = True
        return "已登录慕课网账号"

    # 点击登录按钮
    login_btn = await main_page.query_selector('.js-login-btn')
    if login_btn:
        await login_btn.click()
        message = "请在打开的浏览器中完成登录操作。登录成功后系统将继续运行。"
        print(message)
        max_wait_time = 180
        wait_interval = 5
        waited_time = 0

        while waited_time < max_wait_time:
            try:
                await main_page.wait_for_load_state("networkidle", timeout=5000)
                user_info = await main_page.query_selector('.user-card-box')
                if user_info:
                    is_logged_in = True
                    await asyncio.sleep(2)
                    return "登录成功。"
            except Exception:
                pass
            await asyncio.sleep(wait_interval)
            waited_time += wait_interval

        return "登录等待超时，请重试或手动登录后再继续。"
    else:
        return "未找到登录按钮，请检查网页状态。"


@mcp.tool()
async def search_courses(keywords: str, limit: int = 5) -> str:
    """根据关键词搜索慕课网课程"""
    login_status = await ensure_browser()
    if not login_status:
        return "请先登录慕课网账号"

    try:
        # 先进入主页
        print("正在访问主页...")
        await main_page.goto("https://www.imooc.com", timeout=60000)
        await main_page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # 尝试多种方式找到搜索框
        print("正在查找搜索框...")
        search_selectors = [
            '#js-search-input',
            '.search-input',
            'input[type="search"]',
            'input[placeholder*="搜索"]',
            'input[class*="search"]',
            'input[id*="search"]'
        ]
        
        search_input = None
        for selector in search_selectors:
            print(f"尝试选择器: {selector}")
            search_input = await main_page.query_selector(selector)
            if search_input:
                print(f"找到搜索框，使用选择器: {selector}")
                break
                
        if not search_input:
            return "未找到搜索框，请检查网页结构"

        print(f"正在输入搜索关键词: {keywords}")
        await search_input.fill(keywords)
        
        # 尝试多种方式触发搜索
        print("正在尝试触发搜索...")
        search_btn = await main_page.query_selector('.search-btn')
        if search_btn:
            print("找到搜索按钮，点击搜索")
            await search_btn.click()
        else:
            print("未找到搜索按钮，使用回车键搜索")
            await search_input.press('Enter')
            
        await main_page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # 等待搜索结果页面加载完成
        print("正在等待搜索结果加载...")
        await main_page.wait_for_selector('.search-container', timeout=10000)
        
        # 切换到课程标签页
        course_tab = await main_page.query_selector('.search-nav-item >> text=课程')
        if course_tab:
            await course_tab.click()
            await main_page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

        # 获取课程列表
        course_cards = await main_page.query_selector_all('.search-related-card')
        if not course_cards:
            print("尝试其他选择器...")
            course_cards = await main_page.query_selector_all('.course-item')
        
        if not course_cards:
            return f'未找到与"{keywords}"相关的课程'

        print(f"找到 {len(course_cards)} 个课程")
        results = []
        for card in course_cards[:limit]:
            try:
                # 标题
                title_el = await card.query_selector('.search-related-card-title')
                if not title_el:
                    title_el = await card.query_selector('.search-related-card-name')
                if not title_el:
                    title_el = await card.query_selector('h3, h4')
                title = await title_el.text_content() if title_el else "未知标题"

                # 链接
                link_el = await card.query_selector('a')
                href = await link_el.get_attribute('href') if link_el else ""
                if href:
                    if href.startswith('//'):
                        url = f"https:{href}"
                    elif href.startswith('/'):
                        url = f"https://www.imooc.com{href}"
                    elif href.startswith('http'):
                        url = href
                    else:
                        url = f"https://www.imooc.com/{href}"
                else:
                    url = ""

                # 描述
                desc_el = await card.query_selector('.search-related-card-desc')
                if not desc_el:
                    desc_el = await card.query_selector('.course-desc')
                desc = await desc_el.text_content() if desc_el else ""

                # 价格
                price_el = await card.query_selector('.search-related-card-price')
                if not price_el:
                    price_el = await card.query_selector('.price')
                price = await price_el.text_content() if price_el else "免费"

                # 只添加有效的课程信息
                if title != "未知标题" and url:
                    results.append({
                        "title": title.strip(),
                        "url": url,
                        "description": desc.strip(),
                        "price": price.strip()
                    })
            except Exception as e:
                print(f"处理课程卡片时出错: {str(e)}")
                continue

        if not results:
            return f'未找到与"{keywords}"相关的有效课程信息'

        output = "搜索结果：\n\n"
        for idx, course in enumerate(results, start=1):
            output += f"{idx}. {course['title']}\n"
            if course['description']:
                output += f"   描述: {course['description']}\n"
            output += f"   链接: {course['url']}\n"
            if course['price'] != "免费":
                output += f"   价格: {course['price']}\n"
            output += "\n"

        return output

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"搜索课程时出错: {str(e)}"


@mcp.tool()
async def get_course_details(url: str) -> str:
    """获取指定课程的详细信息"""
    login_status = await ensure_browser()
    if not login_status:
        return "请先登录慕课网账号"

    try:
        await main_page.goto(url, timeout=60000)
        await asyncio.sleep(5)

        title_el = await main_page.query_selector('h2.course-title')
        title = await title_el.text_content() if title_el else "未知标题"

        desc_el = await main_page.query_selector('.course-description')
        description = await desc_el.text_content() if desc_el else ""

        teacher_el = await main_page.query_selector('.teacher-name')
        teacher = await teacher_el.text_content() if teacher_el else ""

        level_el = await main_page.query_selector('.course-infos-item:eq(1)')
        level = await level_el.text_content() if level_el else ""

        duration_el = await main_page.query_selector('.course-infos-item:eq(2)')
        duration = await duration_el.text_content() if duration_el else ""

        students_el = await main_page.query_selector('.target-user')
        students = await students_el.text_content() if students_el else ""

        result = {
            "title": title.strip(),
            "description": description.strip(),
            "teacher": teacher.strip(),
            "level": level.strip(),
            "duration": duration.strip(),
            "students": students.strip(),
            "url": url
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"获取课程详情失败: {str(e)}"


@mcp.tool()
async def search_courses_by_teacher(teacher_name: str, limit: int = 5) -> str:
    """根据教师名称搜索课程"""
    login_status = await ensure_browser()
    if not login_status:
        return "请先登录慕课网账号"

    try:
        search_url = f"https://www.imooc.com/course/list?teacher={teacher_name}"
        await main_page.goto(search_url, timeout=60000)
        await asyncio.sleep(5)

        course_cards = await main_page.query_selector_all('.course-card')
        if not course_cards:
            return f'未找到"{teacher_name}"的课程。'

        results = []
        for card in course_cards[:limit]:
            title_el = await card.query_selector('.course-card-name')
            title = await title_el.text_content() if title_el else "未知标题"

            link_el = await card.query_selector('a')
            href = await link_el.get_attribute('href') if link_el else ""
            url = f"https://www.imooc.com{href}" if href else ""

            desc_el = await card.query_selector('.course-desc')
            desc = await desc_el.text_content() if desc_el else ""

            price_el = await card.query_selector('.price')
            price = await price_el.text_content() if price_el else "免费"

            results.append({
                "title": title.strip(),
                "url": url,
                "description": desc.strip(),
                "price": price.strip()
            })

        output = f"【{teacher_name}】相关课程：\n\n"
        for idx, course in enumerate(results, start=1):
            output += f"{idx}. {course['title']}\n"
            output += f"   描述: {course['description']}\n"
            output += f"   链接: {course['url']}\n"
            output += f"   价格: {course['price']}\n\n"

        return output

    except Exception as e:
        return f"搜索课程时出错: {str(e)}"


@mcp.tool()
async def favorite_course(course_url: str) -> str:
    """收藏指定课程"""
    login_status = await ensure_browser()
    if not login_status:
        return "请先登录慕课网账号"

    try:
        await main_page.goto(course_url, timeout=60000)
        await asyncio.sleep(3)

        # 点击收藏按钮
        like_btn = await main_page.query_selector('.like-btn')
        if like_btn:
            is_liked = await like_btn.get_attribute("data-liked")
            if is_liked == "true":
                return "该课程已收藏"
            await like_btn.click()
            return "课程收藏成功。"
        else:
            return "未找到收藏按钮，请检查页面结构或是否已登录。"

    except Exception as e:
        return f"收藏失败: {str(e)}"


@mcp.tool()
async def search_contents(keyword: str, content_type: str = "all", limit: int = 5) -> str:
    """
    根据关键字搜索内容：
    content_type 支持: all, comment, column, tutorial, note
    """
    search_map = {
        "comment": "https://www.imooc.com/comment/list?search=",
        "column": "https://www.imooc.com/column/list?search=",
        "tutorial": "https://www.imooc.com/article/list?search=",
        "note": "https://www.imooc.com/note/list?search="
    }

    if content_type != "all" and content_type not in search_map:
        return f"不支持的内容类型: {content_type}"

    result = ""
    if content_type == "all":
        for key, base_url in search_map.items():
            url = base_url + keyword
            await main_page.goto(url, timeout=60000)
            await asyncio.sleep(3)

            items = await main_page.query_selector_all(".item-box")[:limit]
            result += f"\n--- {key.upper()} 搜索结果 ---\n"
            if not items:
                result += "无结果\n"
                continue
            for item in items:
                title_el = await item.query_selector("h4 a")
                title = await title_el.text_content() if title_el else "无标题"
                link = await title_el.get_attribute("href") if title_el else ""
                result += f"- {title}: https://www.imooc.com{link}\n"
    else:
        base_url = search_map[content_type]
        url = base_url + keyword
        await main_page.goto(url, timeout=60000)
        await asyncio.sleep(3)

        items = await main_page.query_selector_all(".item-box")[:limit]
        result += f"\n--- {content_type.upper()} 搜索结果 ---\n"
        if not items:
            result += "无结果\n"
        else:
            for item in items:
                title_el = await item.query_selector("h4 a")
                title = await title_el.text_content() if title_el else "无标题"
                link = await title_el.get_attribute("href") if title_el else ""
                result += f"- {title}: https://www.imooc.com{link}\n"

    return result


@mcp.tool()
async def recommend_courses(category: str = "free", limit: int = 5) -> str:
    """
    推荐课程：支持 free(免费？), real(实战？), system(体系？)
    """
    category_map = {
        "free": "https://www.imooc.com/course/list?price=1",
        "real": "https://www.imooc.com/course/list?courseType=2",
        "system": "https://www.imooc.com/special/opencourse"
    }

    if category not in category_map:
        return f"不支持的分类: {category}"

    url = category_map[category]
    await main_page.goto(url, timeout=60000)
    await asyncio.sleep(5)

    if category == "system":
        course_cards = await main_page.query_selector_all('.open-course-item')
    else:
        course_cards = await main_page.query_selector_all('.course-card')

    results = []
    for card in course_cards[:limit]:
        title_el = await card.query_selector('.course-card-name') or await card.query_selector('.title')
        title = await title_el.text_content() if title_el else "未知标题"

        link_el = await card.query_selector('a')
        href = await link_el.get_attribute('href') if link_el else ""
        url = f"https://www.imooc.com{href}" if href else ""

        desc_el = await card.query_selector('.course-desc') or await card.query_selector('.desc')
        desc = await desc_el.text_content() if desc_el else ""

        results.append({
            "title": title.strip(),
            "url": url,
            "description": desc.strip()
        })

    output = f"【推荐 - {category}】课程：\n\n"
    for idx, course in enumerate(results, start=1):
        output += f"{idx}. {course['title']}\n"
        output += f"   描述: {course['description']}\n"
        output += f"   链接: {course['url']}\n\n"

    return output


async def search_command(keywords: str, limit: int = 10):
    """命令行搜索功能"""
    try:
        # 确保已登录
        print("正在登录...")
        login_result = await login()
        print(login_result)
        
        # 搜索课程
        print(f'\n正在搜索"{keywords}"相关课程...')
        search_result = await search_courses(keywords, limit)
        print(search_result)
    except Exception as e:
        print(f"发生错误：{str(e)}")
        import traceback
        traceback.print_exc()


# 启动 MCP 服务
if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) > 1:
            if sys.argv[1] == "login":
                # 直接运行登录功能
                print("正在登录...")
                asyncio.run(login())
            elif sys.argv[1] == "search":
                # 运行搜索功能
                keywords = sys.argv[2] if len(sys.argv) > 2 else "计算机网络"
                limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
                print(f"开始搜索：{keywords}，限制数量：{limit}")
                asyncio.run(search_command(keywords, limit))
        else:
            # 启动 MCP 服务
            print("启动 MCP 服务...")
            mcp.run()
    except Exception as e:
        print(f"程序运行出错：{str(e)}")
        import traceback
        traceback.print_exc()