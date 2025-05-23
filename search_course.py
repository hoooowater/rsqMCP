from fastmcp import FastMCP
import asyncio

async def main():
    mcp = FastMCP("imooc_course_scraper")
    
    # 先登录
    print("正在登录...")
    login_result = await mcp.call("login")
    print(login_result)
    
    # 搜索课程
    print("\n正在搜索计算机网络相关课程...")
    result = await mcp.call("search_courses", {"keywords": "计算机网络", "limit": 10})
    print(result)

if __name__ == "__main__":
    asyncio.run(main()) 