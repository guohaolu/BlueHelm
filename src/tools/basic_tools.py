# -*- coding: utf-8 -*-
import datetime

def get_current_time() -> str:
    """获取当前系统的时间和日期。
    
    Returns:
        str: 当前的时间字符串。
    """
    now = datetime.datetime.now()
    return f"当前时间是 {now.strftime('%Y-%m-%d %H:%M:%S')}。"

def get_weather(city: str) -> str:
    """模拟查询指定城市的天气状况的工具。
    
    Args:
        city (str): 目标城市名称，如 "北京", "上海"。
        
    Returns:
        str: 该城市当前的天气情况描述。
    """
    # 这里我们只提供一个模拟的返回
    weather_db = {
        "北京": "晴，25°C，微风",
        "上海": "多云，28°C，有阵雨",
        "广州": "雷阵雨，30°C，湿度高",
    }
    
    return weather_db.get(city, f"{city}的天气未知，建议直接查看天气预报。")
