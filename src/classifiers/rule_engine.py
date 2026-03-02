# -*- coding: utf-8 -*-
"""
规则引擎（快车道）- 意图分类器
================================
设计思路：
  快车道的核心是「零 LLM 成本」的精确意图识别。当用户输入符合已知固定表达时，
  系统无需调用大模型，直接通过字符串匹配/正则规则返回意图，极大降低延迟。

设计亮点：
  - RuleClassifier 支持关键词列表和正则模式两种匹配维度，层层兜底。
  - IntentType 枚举类型作为多智能体调度决策的唯一令牌（令牌化路由），
    避免调度层对原始字符串进行二次判断，降低耦合度。
  - 面向扩展：新增意图只需在 _RULES 表中添加一行配置，无需修改路由逻辑。
"""

import re
from enum import Enum
from typing import Optional


class IntentType(str, Enum):
    """意图类型枚举。
    
    作为多智能体调度决策的"令牌"，供主规划智能体的路由逻辑使用。
    继承 str，使其可直接被 JSON 序列化，方便在消息结构中传递。
    """
    PLAN_TRIP = "PLAN_TRIP"         # 行程规划意图
    QUERY_INFO = "QUERY_INFO"       # 信息/政策查询意图
    SUBMIT_APPLY = "SUBMIT_APPLY"   # 提交申请意图
    UNKNOWN = "UNKNOWN"             # 未知意图，转入慢车道


# -----------------------------------------------------------------------
# 快车道规则配置表
# 每条规则为 (IntentType, 关键词列表, 正则模式列表)
# 匹配策略：关键词优先，然后正则，有一个命中即视为匹配
# -----------------------------------------------------------------------
_RULES: list[tuple[IntentType, list[str], list[str]]] = [
    (
        IntentType.PLAN_TRIP,
        ["为我规划行程", "规划行程", "帮我订机票", "订机票", "帮我订票", "开始规划"],
        [r"(帮.+规划|订.*(机票|火车票|高铁票))"],
    ),
    (
        IntentType.SUBMIT_APPLY,
        ["为我提申请", "帮我提申请", "提出差申请", "提申请"],
        [r"(提.*申请|申请.*出差)"],
    ),
    (
        IntentType.QUERY_INFO,
        ["政策", "差标", "出差标准", "限额", "报销标准"],
        [r"(政策|差标|限额|报销).*(是什么|查询|怎么|标准)"],
    ),
]


class RuleClassifier:
    """基于规则匹配的快车道意图分类器。
    
    职责：
        仅负责对那些表达模式固定的用户输入进行极速匹配，
        返回一个确定性的 IntentType 或 None（表示快车道未命中，转慢车道）。
    """

    def classify(self, user_input: str) -> Optional[IntentType]:
        """对用户输入进行快车道规则匹配。

        Args:
            user_input (str): 用户的原始输入文本。

        Returns:
            Optional[IntentType]: 命中的意图枚举值，未匹配时返回 None。
        """
        for intent_type, keywords, patterns in _RULES:
            # 1. 关键词精确匹配
            if any(kw in user_input for kw in keywords):
                return intent_type
            # 2. 正则模式匹配
            if any(re.search(p, user_input) for p in patterns):
                return intent_type

        # 快车道未命中，返回 None，由主智能体决定调用慢车道
        return None
