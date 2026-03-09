# 创建一个 ReAct 智能体
import asyncio
import json
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from pydantic import BaseModel, Field

agent = ReActAgent(
    name="Jarvis",
    sys_prompt="你是一个名为 Jarvis 的有用助手。",
    model=DashScopeChatModel(
        model_name="qwen-max",
        api_key=os.environ["DASHSCOPE_API_KEY"],
    ),
    formatter=DashScopeChatFormatter(),
)


# 结构化模型
class Model(BaseModel):
    name: str = Field(description="人物的姓名")
    description: str = Field(description="人物的一句话描述")
    age: int = Field(description="年龄")
    honor: list[str] = Field(description="人物荣誉列表")


async def example_structured_output() -> None:
    """结构化输出示例"""
    res = await agent(
        Msg(
            "user",
            "介绍爱因斯坦",
            "user",
        ),
        structured_model=Model,
    )
    print("\n结构化输出：")
    print(json.dumps(res.metadata, indent=4, ensure_ascii=False))


asyncio.run(example_structured_output())