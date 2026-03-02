# -*- coding: utf-8 -*-
import os
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit
from src.tools.basic_tools import get_current_time, get_weather

def create_react_agent(name: str = "Assistant") -> ReActAgent:
    """初始化并返回一个配置好的 ReAct Agent 实例
    
    Args:
        name (str): Agent的名称，默认为"Assistant"。
        
    Returns:
        ReActAgent: 实例化后的 Agent 对象。
    """
    # 注册工具
    toolkit = Toolkit()
    toolkit.register_tool_function(get_current_time)
    toolkit.register_tool_function(get_weather)

    # 从环境变量获取 API Key，如果没有则回退到一个预设值（仅供演示测试）
    api_key = os.environ.get("DASHSCOPE_API_KEY", "your_dashscope_api_key_here")

    # 配置模型，使用 qwen3-max
    model = DashScopeChatModel(
        model_name="qwen3-max",
        api_key=api_key,
        generate_kwargs={
            "parallel_tool_calls": True, # 使用支持并行工具调用的配置
        },
    )

    # 实例化 Agent，补充 formatter
    agent = ReActAgent(
        name=name,
        sys_prompt="你是一个有用的助手，可以通过调用工具获取必要的信息进而回答用户的问题。",
        model=model,
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    return agent
