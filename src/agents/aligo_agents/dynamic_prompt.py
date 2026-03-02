# -*- coding: utf-8 -*-
"""
动态 Prompt 状态机 - 事项收集智能体专用
========================================
设计思路：
  对应 AliGo 文章"Prompt工程（工程与智能体结合）"章节和架构图中的「动态prompt」模块。

  以往的做法是把所有业务流程、规则、工具调用规范全都塞进一个大 Prompt，
  LLM 需要在全量规则的基础上「实时推理」用户当前处于哪个阶段，负担很重。

  改进方案：用「状态机」的思路，在 Python 层感知用户所处的对话阶段（S1/S2/S3），
  然后「动态组装」只包含该阶段所需信息的精简 Prompt，并注入具体的上下文。
  - LLM 在每一轮只看到「当前阶段最重要的内容」，注意力高度集中。
  - Python 层负责状态转移，确定性强；LLM 负责自然语言处理，灵活性强。
  => 工程确定性 + AI 灵活性的最优平衡点。

状态机说明（对应架构图 S1/S2/S3）：
  S1 - 申请单选择阶段：引导用户选择出差申请单
  S2 - 事项收集阶段：收集并校验行程信息（出发地、事项、返程地）
  S3 - 确认阶段：等待用户最终确认，检测到确认信号则输出进入规划的标签

设计亮点：
  - 使用 dataclass 定义 CollectState，封装阶段编号和阶段上下文数据，
    明确每个阶段「拥有哪些数据」，避免多处代码共享一个大字典。
  - Prompt 组装函数为纯函数（输入确定则输出确定），可完全独立测试。
  - 状态转换逻辑集中在 ItineraryCollectSession 中，方便追踪和审计。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CollectPhase(str, Enum):
    """事项收集状态机的阶段枚举（对应架构图中 S1/S2/S3/S4）。"""
    S1_SELECT_APPLY = "S1"      # 申请单选择阶段
    S2_COLLECT_MATTERS = "S2"   # 事项收集与校验阶段
    S3_CONFIRM = "S3"           # 最终确认阶段
    S4_DONE = "S4"              # 规划完成


@dataclass
class CollectState:
    """事项收集会话的状态容器。

    Attributes:
        phase (CollectPhase): 当前对话阶段。
        apply_id (str | None): 已选择的申请单 ID（S1 完成后赋值）。
        apply_name (str | None): 申请单名称（用于 Prompt 中展示）。
        matters (list[str]): 已收集的出差事项列表（S2 阶段持续追加）。
        verified (bool): 是否通过事项校验（S2 → S3 的转移条件）。
    """
    phase: CollectPhase = CollectPhase.S1_SELECT_APPLY
    apply_id: Optional[str] = None
    apply_name: Optional[str] = None
    matters: list[str] = field(default_factory=list)
    verified: bool = False


# -----------------------------------------------------------------------
# 动态 Prompt 工厂函数（按阶段生成）
# -----------------------------------------------------------------------

# 事项收集 Agent 拥有的工具清单（实际通过 Toolkit 注册，此处仅用于 Prompt 说明）
_TOOL_SPEC = "init_itinerary、matter_check、select_apply、batch_query_place"


def build_s1_prompt(state: CollectState) -> str:
    """S1 申请单选择阶段的 Prompt。

    此阶段只有一个目标：引导用户选择申请单，不涉及任何事项信息。
    Prompt 极简，防止 LLM 过早询问事项或其他无关信息。

    Args:
        state (CollectState): 当前阶段状态（S1 时 apply_id 为 None）。

    Returns:
        str: S1 阶段专用的精简 Prompt。
    """
    return (
        f"## 角色定位\n"
        f"你是差旅事项收集专家，当前处于「申请单选择阶段（S1）」。\n\n"
        f"## 核心原则\n"
        f"你的唯一目标是引导用户选择一个申请单用于行程规划。\n\n"
        f"## 工具调用规范\n"
        f"现在包含：{_TOOL_SPEC}\n\n"
        f"## 当前任务：S1-申请单选择\n"
        f"1. 调用 init_itinerary 初始化申请单，向用户展示选项并输出 <itinerary_select_card>。\n"
        f"2. 当用户用自然语言做出选择后（如'第一个'、'选择开会差旅申请单'），\n"
        f"   必须理解其意图，立即调用 select_apply 工具，并传入正确的 applyId。\n"
        f"   并输出 applyId（按照 <applyId>applyId</applyId> 形式输出）。\n"
        f"3. 在用户做出选择前，不需要询问任何关于行程地点或时间的问题。"
    )


def build_s2_prompt(state: CollectState) -> str:
    """S2 事项收集与校验阶段的 Prompt。

    已获取申请单数据，现在需要收集行程信息（出发地/事项/返程地）并实时校验。
    Prompt 中注入申请单的具体上下文，减少 LLM 的信息补全负担。

    Args:
        state (CollectState): 包含 apply_id 和 apply_name 的当前状态。

    Returns:
        str: S2 阶段专用精简 Prompt，注入申请单上下文。
    """
    matters_str = "\n".join(f"- {m}" for m in state.matters) if state.matters else "（暂无）"
    return (
        f"## 角色定位\n"
        f"你是差旅事项收集专家，当前处于「事项收集阶段（S2）」。\n\n"
        f"## 核心原则\n"
        f"基于当前申请单数据，收集并校验用户的行程信息（出发地、事项、返程地）。\n\n"
        f"## 工具调用规范\n"
        f"现在包含：{_TOOL_SPEC}\n\n"
        f"## 当前申请单情况\n"
        f"选择的申请单数据为：{state.apply_name}（ID: {state.apply_id}）\n"
        f"已收集事项：\n{matters_str}\n\n"
        f"## 当前任务：S2-事项收集\n"
        f"1. 引导用户提供缺失的信息。\n"
        f"2. 每当行程信息有任何更新，必须调用 matter_check 工具进行全量校验。\n"
        f"3. 如果用户想重新选择申请单，重新初始化申请单（回到 S1）。\n"
        f"4. 校验完成后，向用户展示 <itinerary_collect_card> 卡片。"
    )


def build_s3_prompt(state: CollectState) -> str:
    """S3 最终确认阶段的 Prompt。

    事项已经通过 matter_check 校验，只需等待用户最终确认。
    一旦检测到「开始规划」等确认信号，输出 <itinerary_start_planning> 标签触发下游。

    Args:
        state (CollectState): 包含完整事项数据的状态。

    Returns:
        str: S3 阶段专用极简 Prompt。
    """
    matters_str = "\n".join(f"- {m}" for m in state.matters) if state.matters else "（暂无）"
    return (
        f"## 角色定位\n"
        f"你是差旅事项收集专家，当前处于「最终确认阶段（S3）」。\n\n"
        f"## 核心原则\n"
        f"等待用户最终确认，行程已通过 matter_check 校验。\n\n"
        f"## 工具调用规范\n"
        f"现在包含：{_TOOL_SPEC}\n\n"
        f"## 收集事项情况\n"
        f"选择的申请单数据为：{state.apply_name}（ID: {state.apply_id}）\n"
        f"收集事项内容：\n{matters_str}\n\n"
        f"## 当前任务：S3-最终确认\n"
        f"1. 你的目标是等待用户最终确认。\n"
        f"2. 如果用户确认（如'开始规划'），输出 <itinerary_start_planning> 标签。\n"
        f"3. 如果用户提出修改，重新评估并可能调用 matter_check，这会让你回到 S2 状态。"
    )


def build_dynamic_prompt(state: CollectState) -> str:
    """主入口：根据当前状态枚举，分发到对应阶段的 Prompt 生成函数。

    这是「动态 Prompt 状态机」的核心调度函数。外部调用者不需要关心当前处于
    哪个阶段，只需传入 state 对象，即可获得当前会话最适合的 Prompt 文本。

    Args:
        state (CollectState): 当前会话的状态快照。

    Returns:
        str: 适合当前对话阶段的动态 Prompt。
    """
    if state.phase == CollectPhase.S1_SELECT_APPLY:
        return build_s1_prompt(state)
    elif state.phase == CollectPhase.S2_COLLECT_MATTERS:
        return build_s2_prompt(state)
    elif state.phase == CollectPhase.S3_CONFIRM:
        return build_s3_prompt(state)
    else:
        return "行程规划已完成，感谢您的使用！"


class ItineraryCollectSession:
    """事项收集会话管理器（状态机控制器）。

    封装了状态机的转移逻辑，负责在检测到特定关键词或条件时进行阶段切换，
    并在每轮对话时提供当前阶段的动态 Prompt。

    使用方式：
        session = ItineraryCollectSession()
        prompt = session.get_current_prompt()    # 获取当前阶段 Prompt
        session.advance_to_s2("申请单A", "AP001")  # 状态转移：S1 -> S2
        session.add_matter("出发地：杭州，目的地：北京，时间：明天")
        session.set_verified()                   # 事项通过校验 S2 -> S3
    """

    def __init__(self) -> None:
        """初始化事项收集会话，状态从 S1 开始。"""
        self.state = CollectState()

    def get_current_prompt(self) -> str:
        """获取当前对话阶段的动态 Prompt。

        Returns:
            str: 当前阶段专用 Prompt 文本。
        """
        return build_dynamic_prompt(self.state)

    def advance_to_s2(self, apply_name: str, apply_id: str) -> None:
        """触发 S1 → S2 的状态转移（申请单选择完成）。

        Args:
            apply_name (str): 申请单名称。
            apply_id (str): 申请单唯一 ID。
        """
        self.state.apply_name = apply_name
        self.state.apply_id = apply_id
        self.state.phase = CollectPhase.S2_COLLECT_MATTERS

    def add_matter(self, matter: str) -> None:
        """向 S2 阶段的事项列表中追加一条新事项。

        Args:
            matter (str): 用户提供的行程事项描述。
        """
        self.state.matters.append(matter)

    def set_verified(self) -> None:
        """标记事项已通过校验，触发 S2 → S3 的状态转移。"""
        self.state.verified = True
        self.state.phase = CollectPhase.S3_CONFIRM

    def reset_to_s1(self) -> None:
        """重置会话到 S1 状态（用户要求重新选择申请单时调用）。"""
        self.state = CollectState()
