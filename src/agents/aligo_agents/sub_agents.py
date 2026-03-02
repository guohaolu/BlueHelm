# -*- coding: utf-8 -*-
"""
子领域智能体定义
================================
设计思路：
  在 AliGo 多智能体架构中，各子 Agent 专注于单一业务领域，
  符合"单一职责原则"。每个子 Agent 都拥有：
    - 精简的 System Prompt：只关注自己的业务域，大幅降低 LLM 注意力分散。
    - 独立的 InMemoryMemory：各 Agent 维护自己的对话历史，做到领域隔离，
      同时保留通过会话共享 sessionId 按需开放记忆的接口。
    - 绑定对应领域的工具集（MCP 工具在实际生产中通过 toolkit 注入）。

设计亮点：
  通过工厂函数 create_xxx_agent()，将"如何创建"与"如何使用"解耦。
  这与 AliGo 生产代码中的模块独立性设计原则保持一致：
  各 Agent 可独立测试、独立部署，只需在主路由层做组合即可。
"""

import os
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import TextBlock

# -----------------------------------------------------------------------
# 子智能体专用工具（模拟 MCP 服务调用）
# -----------------------------------------------------------------------

def query_trip_plan(destination: str, date: str) -> ToolResponse:
    """查询目标城市的行程规划建议（模拟 MCP 交通路线接口）。

    Args:
        destination (str): 目的地城市名称，如"北京"、"上海"。
        date (str): 出行日期，如"2026-03-10"。

    Returns:
        ToolResponse: 包含行程规划建议的标准响应。
    """
    # 模拟 MCP 服务返回的路线结果
    result = (
        f"为您规划前往 {destination} 的行程（{date}）：\n"
        f"- 推荐高铁：G123（上午 08:00 出发，历时 2.5h，¥553）\n"
        f"- 推荐航班：MU5678（上午 10:00 出发，历时 1.5h，¥820）\n"
        f"- 推荐酒店：全季酒店 {destination} 东站店（¥388/晚，含早餐）\n"
        f"如需一键下单，请回复「确认」。"
    )
    return ToolResponse(content=[TextBlock(type="text", text=result)])


def query_travel_policy(topic: str) -> ToolResponse:
    """查询企业差旅政策或报销标准（模拟 RAG 知识库检索）。

    Args:
        topic (str): 查询的政策主题，如"差标"、"机票报销"、"酒店限额"。

    Returns:
        ToolResponse: 包含政策查询结果的标准响应。
    """
    policy_db = {
        "差标": "差旅标准：国内经济舱机票，酒店单价不超过 500 元/晚（北上广深 600 元/晚）。",
        "机票": "机票报销政策：需提前 7 天购票，超出标准部分由员工自行承担。",
        "酒店": "酒店限额：非重点城市上限 400 元/晚，含早餐可折算后报销。",
    }
    # 模糊查询，查找包含关键词的政策
    result = next(
        (v for k, v in policy_db.items() if k in topic),
        f"未找到关于「{topic}」的相关政策，建议咨询人事部门。",
    )
    return ToolResponse(content=[TextBlock(type="text", text=result)])


# -----------------------------------------------------------------------
# 子 Agent 工厂函数
# -----------------------------------------------------------------------

def _create_model(model_name: str = "qwen3-max") -> DashScopeChatModel:
    """创建共用的 DashScope 大模型实例。

    Args:
        model_name (str): DashScope 的模型名称。

    Returns:
        DashScopeChatModel: 初始化完成的模型实例。
    """
    api_key = os.environ.get("DASHSCOPE_API_KEY", "your_api_key_here")
    return DashScopeChatModel(
        model_name=model_name,
        api_key=api_key,
    )


def create_trip_plan_agent() -> ReActAgent:
    """创建行程规划子智能体（TripPlanAgent）。

    该智能体负责：
    - 根据用户提供的目的地和时间，调用交通规划 MCP 工具，生成出行建议。
    - 精简 Prompt：只专注行程规划，不涉及政策查询或申请提交等逻辑，
      有效降低 LLM 注意力分散，提升规划输出的准确率。

    Returns:
        ReActAgent: 配置完成的行程规划智能体。
    """
    toolkit = Toolkit()
    toolkit.register_tool_function(query_trip_plan)

    return ReActAgent(
        name="TripPlanAgent",
        sys_prompt=(
            "你是一个专业的差旅行程规划专家，专注于帮助用户规划出行方案。\n"
            "你只需要完成以下任务：\n"
            "1. 询问并确认用户的目的地和出行日期。\n"
            "2. 调用 query_trip_plan 工具生成交通和酒店建议。\n"
            "3. 将结果以简洁、清晰的方式呈现给用户。\n"
            "注意：不要处理任何与行程无关的请求，如政策查询、申请提交等。"
        ),
        model=_create_model(),
        formatter=DashScopeChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )


def create_info_query_agent() -> ReActAgent:
    """创建信息/政策查询子智能体（InfoQueryAgent）。

    该智能体负责：
    - 接收用户提出的差旅政策、报销标准等问题，调用 RAG 知识库工具进行检索。
    - 采用 Handoffs 模式：接收主 Agent 的意图后，独立完成从问题到答案的全流程。

    Returns:
        ReActAgent: 配置完成的政策信息查询智能体。
    """
    toolkit = Toolkit()
    toolkit.register_tool_function(query_travel_policy)

    return ReActAgent(
        name="InfoQueryAgent",
        sys_prompt=(
            "你是一个专业的企业差旅政策顾问，负责回答用户关于差旅标准和报销政策的问题。\n"
            "你只需要完成以下任务：\n"
            "1. 理解用户的政策查询需求。\n"
            "2. 调用 query_travel_policy 工具从知识库中检索相关政策。\n"
            "3. 以专业、准确的语言向用户解释政策内容。\n"
            "注意：不要处理行程规划、申请提交等与政策查询无关的请求。"
        ),
        model=_create_model(),
        formatter=DashScopeChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )
