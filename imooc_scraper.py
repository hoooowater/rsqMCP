# -*- coding: utf-8 -*-
import asyncio
import os
from typing import Optional, List, Dict
from dataclasses import dataclass
from urllib.parse import quote
from playwright.async_api import async_playwright
from fastmcp import FastMCP

# ����
BROWSER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_data")
os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

# ��ʼ�� MCP ����
mcp = FastMCP("imooc_course_scraper")

# ������
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
        """ȷ�������������"""
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
        """��¼Ľ����"""
        await self.ensure_browser()
        
        if self.is_logged_in:
            return "�ѵ�¼Ľ�����˺�"
        
        await self.page.goto("https://www.imooc.com")
        await asyncio.sleep(2)
        
        login_button = await self.page.query_selector('text="��¼"')
        if login_button:
            print("�������������ɵ�¼����...")
            await login_button.click()
            
            max_wait_time = 180
            wait_interval = 2
            waited_time = 0
            
            while waited_time < max_wait_time:
                await asyncio.sleep(wait_interval)
                if not await self.page.query_selector('text="��¼"'):
                    self.is_logged_in = True
                    return "��¼�ɹ���"
                waited_time += wait_interval
            
            return "��¼�ȴ���ʱ��������"
        else:
            self.is_logged_in = True
            return "�ѵ�¼Ľ�����˺�"
    
    async def search_courses(self, keywords: str, limit: int = 10) -> List[Course]:
        """�����γ�"""
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
                    title = await title_el.text_content() if title_el else "δ֪����"
                    
                    desc_el = await card.query_selector('.course-card-desc')
                    desc = await desc_el.text_content() if desc_el else "������"
                    
                    price_el = await card.query_selector('.course-card-price')
                    price = await price_el.text_content() if price_el else "���"
                    
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
                    print(f"����γ�ʱ����{str(e)}")
                    continue
        except Exception as e:
            print(f"�����γ�ʱ����{str(e)}")
        
        return courses

# MCP����
@mcp.tool()
async def login() -> str:
    """��¼Ľ�����˺�"""
    scraper = ImoocScraper()
    return await scraper.login()

@mcp.tool()
async def search_courses(keywords: str, limit: int = 10) -> str:
    """����Ľ�����γ�"""
    scraper = ImoocScraper()
    courses = await scraper.search_courses(keywords, limit)
    
    if not courses:
        return f"δ�ҵ���"{keywords}"��صĿγ�"
    
    output = f"�ҵ� {len(courses)} ����ؿγ̣�\n\n"
    for i, course in enumerate(courses, 1):
        output += f"{i}. {course.title}\n"
        output += f"   ������{course.description}\n"
        output += f"   �۸�{course.price}\n"
        output += f"   ���ӣ�{course.url}\n\n"
    
    return output

# ֱ�����нű�ʱ�����
async def main():
    """ֱ�����нű�ʱ��������"""
    scraper = ImoocScraper()
    await scraper.login()
    
    while True:
        try:
            keywords = input("\n������Ҫ�����Ŀγ̹ؼ��ʣ�ֱ�ӻس��˳�����").strip()
            if not keywords:
                break
            
            courses = await scraper.search_courses(keywords)
            if courses:
                print(f"\n�ҵ� {len(courses)} ����ؿγ̣�\n")
                for i, course in enumerate(courses, 1):
                    print(f"{i}. {course.title}")
                    print(f"   ������{course.description}")
                    print(f"   �۸�{course.price}")
                    print(f"   ���ӣ�{course.url}\n")
            else:
                print(f"\nδ�ҵ���"{keywords}"��صĿγ�")
        except Exception as e:
            print(f"��������{str(e)}")
        
        choice = input("\n�Ƿ����������(y/n): ").strip().lower()
        if choice != 'y':
            break

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        # ��Ϊ����������
        mcp.run()
    else:
        # ��Ϊ�����ű�����
        asyncio.run(main()) 