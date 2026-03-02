# -*- coding: utf-8 -*-
"""
主规划智能体 - 动态 Prompt 路由器 (MainPlanAgent)
====================================================
设计思路：
  对应 AliGo 架构图中的"主智能体 MainPlanAgent"层。这是整个多 Agent 架构的
  核心协调者，承担以下职责：
    1. 快慢车道分发：先过规则引擎（快车道），命中则直接路由；未命中则调用
       LLM（慢车道）进行意图识别，再二次路由。
    2. 动态 Prompt 组装：根据快慢车道的分类结果「运行时」生成不同的 Prompt
       模板，而非使用一份静态的"万能 Prompt"。这是从 50% 提升到 90%+ 准确率
       的核心工程手段——LLM 的注意力始终聚焦在当前最关键的业务链路上。
    3. 路由结果聚合：接收子 Agent 的输出后，统一汇总为结构化的响应返回。

设计亮点：
  - 快慢车道的判断逻辑「完全在宿主语言（Python）中实现」，确定性高。
    LLM 只负责处理规则引擎"看不懂"的模糊输入，角色定位清晰。
  - Prompt 模板分为两套（简单意图/复杂意图）并以函数形式独立管理，
    便于 Prompt 工程师单独迭代而不影响路由逻辑。
  - 动态 Prompt 函数是「无副作用的纯函数」（输入确定则输出确定），
    可独立做单元测试，结果稳定可预期。
"""

import asyncio
import json
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel

from src.classifiers.rule_engine import IntentType, RuleClassifier
from src.agents.aligo_agents.sub_agents import create_trip_plan_agent, create_info_query_agent

# -----------------------------------------------------------------------
# 动态 Prompt 模板模块
# -----------------------------------------------------------------------

# 所有已知子 Agent 的名称列表（供慢车道 LLM 意图识别使用）
_KNOWN_AGENTS = ["TripPlanAgent", "InfoQueryAgent"]


def _get_simple_intent_prompt(intent: IntentType) -> str:
    """快车道：为已明确的意图生成一个直接的路由指令 Prompt。

    设计理由：
        当用户意图已经由规则引擎「确定性」地识别出来时，
        Prompt 只需要告诉 LLM「执行路由」，
        而不需要它去「思考意图是什么」，大幅减少无效推理 Token。

    Args:
        intent (IntentType): 规则引擎匹配到的意图类型。

    Returns:
        str: 精简的路由指令 Prompt。
    """
    agent_mapping = {
        IntentType.PLAN_TRIP: "TripPlanAgent",
        IntentType.QUERY_INFO: "InfoQueryAgent",
        IntentType.SUBMIT_APPLY: "TripPlanAgent",  # 例：提交申请也由行程规划 Agent 处理  
    }
    target_agent = agent_mapping.get(intent, "TripPlanAgent")
    return (
        f"用户意图已明确为「{intent.value}」。\n"
        f"请直接调用 route_to_agent 工具，将任务转交给 {target_agent}，"
        f"并原封不动地传递用户的原始输入作为任务描述。\n"
        f"不需要进行任何额外的意图分析。"
    )


def _get_complex_intent_prompt(user_input: str) -> str:
    """慢车道：为复杂/模糊意图生成两段式（推理+决策）的 Prompt。

    设计理由：
        AliGo 实践中，要求 LLM in「显式推理」再做「决策」（两段式结构），
        通过强制生成思考过程后再产出决策 JSON，效果明显优于直接要求 JSON 输出。
        这对应 Chain-of-Thought 技术在路由场景的工程化落地。

    Args:
        user_input (str): 用户的原始输入。

    Returns:
        str: 引导 LLM 进行两段式（推理+决策 JSON）输出的 Prompt。
    """
    agents_desc = "\n".join([
        "- TripPlanAgent：负责行程规划、机票/酒店预订、路线推荐等出行相关需求。",
        "- InfoQueryAgent：负责企业差旅政策、报销标准、审批规则等信息查询需求。",
    ])
    return (
        f"你是一个多智能体差旅系统的主规划协调器。\n\n"
        f"当前可用的子智能体：\n{agents_desc}\n\n"
        f"用户输入：「{user_input}」\n\n"
        f"请按以下两段式格式输出：\n"
        f"[推理过程]\n逐步分析用户的意图，明确需要哪个子智能体处理，以及原因。\n\n"
        f"[决策 JSON]\n```json\n"
        f'{{"target_agent": "<agent名称>", "reason": "<简短原因>", "rewritten_query": "<改写后的标准化问题>"}}\n'
        f"```\n\n"
        f"注意：rewritten_query 需要补全上下文信息，将口语化的表达转化为结构化的查询。"
    )


def get_prompt_main_plan(user_input: str, classifier: RuleClassifier) -> tuple[str, IntentType | None]:
    """主规划智能体的动态 Prompt 生成函数（快慢车道入口）。

    这是 AliGo 架构最核心的工程函数。它将快慢车道的决策逻辑与
    Prompt 模板的选择完全封装在一个函数里：
    - 快车道命中 → 返回简单路由 Prompt（确定性高，延迟低）
    - 快车道未命中 → 返回两段式意图识别 Prompt（引导 LLM 深度分析）

    Args:
        user_input (str): 用户的原始输入文本。
        classifier (RuleClassifier): 规则引擎分类器实例。

    Returns:
        tuple[str, IntentType | None]: (动态生成的 Prompt, 快车道命中的意图或 None)
    """
    rule_match_result = classifier.classify(user_input)

    if rule_match_result:
        # 快车道：规则匹配成功，生成简单意图 Prompt
        return _get_simple_intent_prompt(rule_match_result), rule_match_result
    else:
        # 慢车道：规则匹配失败，生成复杂意图 Prompt，交由 LLM 分析
        return _get_complex_intent_prompt(user_input), None


# -----------------------------------------------------------------------
# 主路由智能体实现
# -----------------------------------------------------------------------

class MainRouter:
    """主规划路由器：协调快慢车道分发和子 Agent 调用。

    该类直接对应 AliGo 文章中"以主规划智能体为核心，协调多个专业化子智能体
    协同工作，形成完整的差旅规划解决方案"的设计。

    重要设计决策：
        MainRouter 自身「不是」一个 ReActAgent，而是一个「编排层」。
        它持有 RuleClassifier 和各个子 Agent 的引用，在 Python 层面控制流程，
        而不是把所有路由逻辑都交给 LLM。
        -> 工程确定性 + AI 灵活性 的有效平衡。
    """

    def __init__(self) -> None:
        """初始化主路由器，加载分类器和所有子 Agent。"""
        self.classifier = RuleClassifier()
        self.trip_plan_agent = create_trip_plan_agent()
        self.info_query_agent = create_info_query_agent()

        # 意图 -> 子 Agent 的路由表（支持运行时扩展）
        self._routing_table: dict[IntentType, ReActAgent] = {
            IntentType.PLAN_TRIP: self.trip_plan_agent,
            IntentType.SUBMIT_APPLY: self.trip_plan_agent,
            IntentType.QUERY_INFO: self.info_query_agent,
        }

        # 慢车道：需要 LLM 进行意图识别的模型（可使用轻量级模型降低成本）
        api_key = os.environ.get("DASHSCOPE_API_KEY", "your_api_key_here")
        self._intent_model = DashScopeChatModel(
            model_name="qwen3-max",  # 对应 AliGo 文章推荐的 Qwen3 系列
            api_key=api_key,
        )
        self._formatter = DashScopeChatFormatter()

    def _parse_llm_decision(self, response_text: str) -> dict:
        """从 LLM 的两段式输出中提取决策 JSON。

        Args:
            response_text (str): LLM 的原始输出文本（包含推理过程和 JSON 块）。

        Returns:
            dict: 解析出的决策字典，格式为 {target_agent, reason, rewritten_query}。
        """
        try:
            # 提取 ``` 代码块中的 JSON
            json_start = response_text.find("```json")
            json_end = response_text.find("```", json_start + 7)
            if json_start != -1 and json_end != -1:
                json_str = response_text[json_start + 7:json_end].strip()
                return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            pass
        # 兜底：返回默认路由到行程规划
        return {"target_agent": "TripPlanAgent", "reason": "无法解析决策", "rewritten_query": response_text}

    async def _slow_lane_intent_recognition(self, user_input: str) -> tuple[str, str]:
        """慢车道：调用 LLM 进行两段式意图识别。

        Args:
            user_input (str): 用户的原始输入文本。

        Returns:
            tuple[str, str]: (target_agent_name, rewritten_query)
        """
        complex_prompt = _get_complex_intent_prompt(user_input)
        messages = self._formatter.format_messages(
            [Msg("user", complex_prompt, "user")]
        )
        response = await self._intent_model.acall(messages)
        response_text = response.choices[0].message.content or ""

        print(f"\n[慢车道 LLM 意图识别]\n{response_text[:300]}...")
        decision = self._parse_llm_decision(response_text)
        return decision.get("target_agent", "TripPlanAgent"), decision.get("rewritten_query", user_input)

    async def route(self, user_input: str) -> Msg:
        """核心路由方法：接收用户输入，经快慢车道判断后转交给对应子 Agent。

        流程：
            1. 规则引擎（快车道）尝试匹配；
            2. 命中 → 直接路由对应子 Agent；
            3. 未命中 → 慢车道 LLM 识别意图 → 再次路由；
            4. 子 Agent 处理并返回结果。

        Args:
            user_input (str): 用户的原始输入文本。

        Returns:
            Msg: 子 Agent 处理后的响应消息。
        """
        query_to_use = user_input
        intent = self.classifier.classify(user_input)

        if intent:
            print(f"\n[快车道命中] 意图：{intent.value}")
            target_agent = self._routing_table.get(intent, self.trip_plan_agent)
        else:
            print("\n[快车道未命中，启动慢车道 LLM 分析...]")
            agent_name, query_to_use = await self._slow_lane_intent_recognition(user_input)
            # 根据 LLM 返回的 agent 名称查找对应的 Agent 实例
            target_agent = {
                "TripPlanAgent": self.trip_plan_agent,
                "InfoQueryAgent": self.info_query_agent,
            }.get(agent_name, self.trip_plan_agent)
            print(f"[慢车道决策] 路由到：{agent_name}，改写 query：{query_to_use}")

        print(f"\n[调用子 Agent: {target_agent.name}]")
        user_msg = Msg("user", query_to_use, "user")
        response = await target_agent(user_msg)
        return response
