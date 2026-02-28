# -*- coding: utf-8 -*-
import os
import unittest
from agentscope.agent import ReActAgent
from src.agents.react_agent import create_react_agent

class TestReActAgentFactory(unittest.TestCase):
    def test_create_react_agent(self):
        """测试 ReAct Agent 能否被正确实例化且工具成功挂载"""
        # 由于我们只测试工厂方法及其基础属性构造，这里不直接发请求测试大模型调用，因此不需要真实的 API_KEY
        os.environ["DASHSCOPE_API_KEY"] = "dummy_key_for_test"

        agent = create_react_agent(name="TestAgent")
        
        # 验证返回类型
        self.assertIsInstance(agent, ReActAgent)
        
        # 验证 Agent 名称是否符合设置
        self.assertEqual(agent.name, "TestAgent")
        
        # 这个断言验证一下大模型是否被正确关联（即使是虚假的 Key）
        self.assertIsNotNone(agent.model)
        
        # 在 AgentScope 内部的 Toolkit，验证至少装备了我们的两个基础工具（外加两个可能通过 agent 自己装备的基础工具等共 >= 2）
        from src.tools.basic_tools import get_current_time, get_weather
        
        # 简单校验 JSON Schemas 中包含特定函数名称即可证明工具挂载
        schemas = agent.toolkit.get_json_schemas()
        function_names = [schema["function"]["name"] for schema in schemas]
        self.assertIn(get_current_time.__name__, function_names)
        self.assertIn(get_weather.__name__, function_names)

if __name__ == '__main__':
    unittest.main()
