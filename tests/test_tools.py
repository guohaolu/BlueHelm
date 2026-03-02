# -*- coding: utf-8 -*-
import unittest
from agentscope.tool import ToolResponse
from src.tools.basic_tools import get_current_time, get_weather

class TestBasicTools(unittest.TestCase):
    def test_get_current_time(self):
        """测试获取当前时间工具是否返回正确的 ToolResponse"""
        result = get_current_time()
        self.assertIsInstance(result, ToolResponse)
        text_content = result.content[0]["text"]
        self.assertIn("当前时间是", text_content)

    def test_get_weather_known_city(self):
        """测试针对已知城市查询天气的返回结果"""
        result = get_weather("北京")
        self.assertIsInstance(result, ToolResponse)
        text_content = result.content[0]["text"]
        self.assertNotIn("未知", text_content)
        self.assertEqual("晴，25°C，微风", text_content)

    def test_get_weather_unknown_city(self):
        """测试查询未知城市天气的容错情况"""
        city = "哈尔滨"
        result = get_weather(city)
        self.assertIsInstance(result, ToolResponse)
        text_content = result.content[0]["text"]
        self.assertIn("天气未知", text_content)

if __name__ == '__main__':
    unittest.main()
