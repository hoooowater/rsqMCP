from fastmcp import FastMCP
import asyncio

async def main():
    mcp = FastMCP("imooc_course_scraper")
    
    # �ȵ�¼
    print("���ڵ�¼...")
    login_result = await mcp.call("login")
    print(login_result)
    
    # �����γ�
    print("\n�������������������ؿγ�...")
    result = await mcp.call("search_courses", {"keywords": "���������", "limit": 10})
    print(result)

if __name__ == "__main__":
    asyncio.run(main()) 