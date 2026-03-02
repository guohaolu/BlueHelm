# -*- coding: utf-8 -*-
import datetime
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

def get_current_time() -> ToolResponse:
    """获取当前系统的时间和日期。
    
    Returns:
        ToolResponse: 包装当前时间的标准内容格式。
    """
    now = datetime.datetime.now()
    content = f"当前时间是 {now.strftime('%Y-%m-%d %H:%M:%S')}。"
    return ToolResponse(
        content=[TextBlock(type="text", text=content)]
    )

def get_weather(city: str) -> ToolResponse:
    """模拟查询指定城市的天气状况的工具。
    
    Args:
        city (str): 目标城市名称，如 "北京", "上海"。
        
    Returns:
        ToolResponse: 包装该城市天气的标准内容格式。
    """
    # 这里我们只提供一个模拟的返回
    weather_db = {
        "北京": "晴，25°C，微风",
        "上海": "多云，28°C，有阵雨",
        "广州": "雷阵雨，30°C，湿度高",
    }
    
    content = weather_db.get(city, f"{city}的天气未知，建议直接查看天气预报。")
    return ToolResponse(
        content=[TextBlock(type="text", text=content)]
    )
