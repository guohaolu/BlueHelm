# -*- coding: utf-8 -*-
import asyncio
import os
import sys

# 确保包能够被正确导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentscope.message import Msg
from src.agents.react_agent import create_react_agent

async def main():
    print("正在初始化 ReAct Agent ...")
    agent = create_react_agent(name="BlueHelm_Assistant")
    
    print("=" * 40)
    print("💬 对话开始 (输入 'exit' 或 'quit' 退出)")
    print("💡 提示: 尝试询问当前时间或北京的天气情况以验证工具调用能力")
    print("=" * 40)
    
    while True:
        user_input = input("\n[User]: ")
        if user_input.lower() in ["exit", "quit"]:
            print("再见！")
            break
            
        if not user_input.strip():
            continue
            
        # 封装用户消息
        msg = Msg("user", user_input, "user")
        
        try:
            # 调用 Agent
            response = await agent(msg)
            # Response 会带有 format 后的格式输出到控制台（通常由于内部 formatter）
            # 我们也可以显式打印
            print(f"\n[{agent.name}]: {response.content}")
        except Exception as e:
            print(f"\n[Error]: 调用 Agent 时发生错误: {e}")
            print("请检查 DASHSCOPE_API_KEY 环境变量是否已正确配置。")

if __name__ == "__main__":
    asyncio.run(main())
