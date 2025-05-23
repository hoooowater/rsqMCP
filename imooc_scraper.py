# -*- coding: utf-8 -*-
import asyncio
import os
from typing import Optional, List, Dict
from dataclasses import dataclass
from urllib.parse import quote
from playwright.async_api import async_playwright
from fastmcp import FastMCP

# 配置
BROWSER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_data")
os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

# 初始化 MCP 服务
mcp = FastMCP("imooc_course_scraper")

# 数据类
@dataclass
class Course:
    title: str
    description: str
    price: str
    url: str

class ImoocScraper:
    def __init__(self):
        self.browser_context = None
        self.page = None
        self.is_logged_in = False
    
    async def ensure_browser(self):
        """确保浏览器已启动"""
        if not self.browser_context:
            p = await async_playwright().start()
            self.browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_DATA_DIR,
                headless=False
            )
            if self.browser_context.pages:
                self.page = self.browser_context.pages[0]
            else:
                self.page = await self.browser_context.new_page()
    
    async def login(self) -> str:
        """登录慕课网"""
        await self.ensure_browser()
        
        if self.is_logged_in:
            return "已登录慕课网账号"
        
        await self.page.goto("https://www.imooc.com")
        await asyncio.sleep(2)
        
        login_button = await self.page.query_selector('text="登录"')
        if login_button:
            print("请在浏览器中完成登录操作...")
            await login_button.click()
            
            max_wait_time = 180
            wait_interval = 2
            waited_time = 0
            
            while waited_time < max_wait_time:
                await asyncio.sleep(wait_interval)
                if not await self.page.query_selector('text="登录"'):
                    self.is_logged_in = True
                    return "登录成功！"
                waited_time += wait_interval
            
            return "登录等待超时，请重试"
        else:
            self.is_logged_in = True
            return "已登录慕课网账号"
    
    async def search_courses(self, keywords: str, limit: int = 10) -> List[Course]:
        """搜索课程"""
        await self.ensure_browser()
        
        if not self.is_logged_in:
            await self.login()
        
        search_url = f"https://www.imooc.com/course/list?words={quote(keywords)}"
        await self.page.goto(search_url)
        await asyncio.sleep(3)
        
        courses = []
        try:
            course_cards = await self.page.query_selector_all('.course-card')
            
            for card in course_cards[:limit]:
                try:
                    title_el = await card.query_selector('.course-card-name')
                    title = await title_el.text_content() if title_el else "未知标题"
                    
                    desc_el = await card.query_selector('.course-card-desc')
                    desc = await desc_el.text_content() if desc_el else "无描述"
                    
                    price_el = await card.query_selector('.course-card-price')
                    price = await price_el.text_content() if price_el else "免费"
                    
                    link_el = await card.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    url = f"https://www.imooc.com{href}" if href else ""
                    
                    courses.append(Course(
                        title=title.strip(),
                        description=desc.strip(),
                        price=price.strip(),
                        url=url
                    ))
                except Exception as e:
                    print(f"处理课程时出错：{str(e)}")
                    continue
        except Exception as e:
            print(f"搜索课程时出错：{str(e)}")
        
        return courses

# MCP工具
@mcp.tool()
async def login() -> str:
    """登录慕课网账号"""
    scraper = ImoocScraper()
    return await scraper.login()

@mcp.tool()
async def search_courses(keywords: str, limit: int = 10) -> str:
    """搜索慕课网课程"""
    scraper = ImoocScraper()
    courses = await scraper.search_courses(keywords, limit)
    
    if not courses:
        return f"未找到与"{keywords}"相关的课程"
    
    output = f"找到 {len(courses)} 个相关课程：\n\n"
    for i, course in enumerate(courses, 1):
        output += f"{i}. {course.title}\n"
        output += f"   描述：{course.description}\n"
        output += f"   价格：{course.price}\n"
        output += f"   链接：{course.url}\n\n"
    
    return output

# 直接运行脚本时的入口
async def main():
    """直接运行脚本时的主函数"""
    scraper = ImoocScraper()
    await scraper.login()
    
    while True:
        try:
            keywords = input("\n请输入要搜索的课程关键词（直接回车退出）：").strip()
            if not keywords:
                break
            
            courses = await scraper.search_courses(keywords)
            if courses:
                print(f"\n找到 {len(courses)} 个相关课程：\n")
                for i, course in enumerate(courses, 1):
                    print(f"{i}. {course.title}")
                    print(f"   描述：{course.description}")
                    print(f"   价格：{course.price}")
                    print(f"   链接：{course.url}\n")
            else:
                print(f"\n未找到与"{keywords}"相关的课程")
        except Exception as e:
            print(f"发生错误：{str(e)}")
        
        choice = input("\n是否继续搜索？(y/n): ").strip().lower()
        if choice != 'y':
            break

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        # 作为服务器运行
        mcp.run()
    else:
        # 作为独立脚本运行
        asyncio.run(main()) 