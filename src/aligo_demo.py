# -*- coding: utf-8 -*-
"""
AliGo 风格多智能体架构演示入口
================================
本文件将以下模块串联起来，演示完整的业务流程：
  1. 快慢车道意图路由（MainRouter）
  2. ReActAgent Hook 拦截  + TaskCollector 思考链追踪（Hooks）
  3. 动态 Prompt 状态机（ItineraryCollectSession）的快速功能展示

注意：演示模式下不会真正发起 LLM 调用的模块（慢车道/子 Agent）
       需要正确配置 DASHSCOPE_API_KEY 环境变量才能完整运行。
       快车道路由逻辑、规则引擎、状态机模块在无 API_KEY 下也会正常演示。
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.classifiers.rule_engine import RuleClassifier, IntentType
from src.agents.aligo_agents.main_router import get_prompt_main_plan
from src.agents.aligo_agents.hooks import TaskCollector, TaskStatus
from src.agents.aligo_agents.dynamic_prompt import (
    ItineraryCollectSession, CollectPhase
)


# -----------------------------------------------------------------------
# 演示模块 1：快慢车道规则引擎展示
# -----------------------------------------------------------------------
def demo_rule_engine() -> None:
    """演示快车道规则引擎的分类结果。"""
    print("\n" + "="*60)
    print("  [Demo 1] 快慢车道规则引擎（快车道无 LLM 成本）")
    print("="*60)

    classifier = RuleClassifier()
    test_inputs = [
        "为我规划行程",                          # 快车道：PLAN_TRIP
        "帮我提申请",                            # 快车道：SUBMIT_APPLY
        "出差政策是什么",                         # 快车道：QUERY_INFO
        "其实我想了解一下差旅报销有什么标准",       # 快车道：QUERY_INFO
        "我下周要去北京参加一个技术会议，请帮我安排", # 慢车道：None
        "这次行程好贵，能不能选便宜点的方案",       # 慢车道：None
    ]

    for user_input in test_inputs:
        intent = classifier.classify(user_input)
        lane = "[Fast] 快车道" if intent else "[Slow] 慢车道"
        print(f"  {lane} | 输入：「{user_input[:25]}...」" if len(user_input) > 25
              else f"  {lane} | 输入：「{user_input}」")
        if intent:
            print(f"          意图：{intent.value}")
        else:
            print(f"          -> 转 LLM 进行深度意图分析")
        print()


# -----------------------------------------------------------------------
# 演示模块 2：动态 Prompt 生成展示
# -----------------------------------------------------------------------
def demo_dynamic_prompt() -> None:
    """演示根据快慢车道结果生成对应的动态 Prompt。"""
    print("\n" + "="*60)
    print("  [Demo 2] 主规划智能体的动态 Prompt 组装")
    print("="*60)

    classifier = RuleClassifier()

    cases = [
        "帮我订去北京的机票",
        "这次出差的餐费怎么报销",
    ]

    for user_input in cases:
        prompt, intent = get_prompt_main_plan(user_input, classifier)
        lane = "快车道" if intent else "慢车道"
        print(f"  用户输入：「{user_input}」")
        print(f"  -> [{lane}] 动态 Prompt 片段（前 200 字）：")
        print(f"  {prompt[:200]}...")
        print()


# -----------------------------------------------------------------------
# 演示模块 3：动态 Prompt 状态机（S1→S2→S3）展示
# -----------------------------------------------------------------------
def demo_state_machine() -> None:
    """演示事项收集状态机的阶段切换和 Prompt 动态组装。"""
    print("\n" + "="*60)
    print("  [Demo 3] 事项收集动态 Prompt 状态机（S1/S2/S3）")
    print("="*60)

    session = ItineraryCollectSession()
    phases = []

    # S1
    phases.append(("S1 申请单选择阶段", session.get_current_prompt()[:300]))

    # 模拟用户选了申请单，触发 S1 -> S2
    session.advance_to_s2(apply_name="北京技术会议差旅申请", apply_id="AP-2026-001")
    session.add_matter("出发地：杭州，目的地：北京，出发日期：2026-03-10，返程日期：2026-03-12")
    phases.append(("S2 事项收集阶段", session.get_current_prompt()[:300]))

    # 模拟事项校验通过，触发 S2 -> S3
    session.set_verified()
    phases.append(("S3 最终确认阶段", session.get_current_prompt()[:300]))

    for phase_name, prompt_preview in phases:
        print(f"  [{phase_name}]")
        print(f"  Prompt 预览：\n  {prompt_preview}...\n")


# -----------------------------------------------------------------------
# 演示模块 4：TaskCollector 发布-订阅机制展示
# -----------------------------------------------------------------------
async def demo_task_collector() -> None:
    """演示 TaskCollector 的发布-订阅模式追踪工具调用状态。"""
    print("\n" + "="*60)
    print("  [Demo 4] TaskCollector 实时思考链追踪（发布-订阅）")
    print("="*60)

    received_events: list[str] = []

    async def my_subscriber(task) -> None:
        """模拟一个消费者（如 SSE 接口）接收 task 状态更新。"""
        event_str = f"[{task.status.value}] 工具：{task.tool_name}"
        received_events.append(event_str)
        print(f"  [RECV] 订阅者收到事件 -> {event_str}")
        if task.output:
            print(f"         输出：{task.output[:80]}...")

    collector = TaskCollector()
    collector.subscribe(my_subscriber)

    # 模拟一次完整的 tool_use -> tool_result 生命周期
    await collector.add_tool_use(
        tool_id="TOOL-001",
        tool_name="query_trip_plan",
        tool_input={"destination": "北京", "date": "2026-03-10"},
    )
    await asyncio.sleep(0.1)  # 模拟工具执行耗时
    await collector.add_tool_result(
        tool_id="TOOL-001",
        output="为您规划前往北京的行程：推荐高铁 G123（08:00，553元），推荐酒店全季（388元/晚）",
        success=True,
    )

    print(f"\n  任务追踪汇总（共 {len(received_events)} 个事件）：")
    for e in received_events:
        print(f"    - {e}")


# -----------------------------------------------------------------------
# 主入口（对话模式，需要配置 DASHSCOPE_API_KEY）
# -----------------------------------------------------------------------
async def interactive_mode() -> None:
    """交互式对话模式：需要有效的 DASHSCOPE_API_KEY 才能调用大模型。"""
    from src.agents.aligo_agents.main_router import MainRouter
    from src.agents.aligo_agents.hooks import TaskCollector, register_task_hook

    print("\n" + "="*60)
    print("  AliGo 多智能体差旅助手 - 交互模式")
    print("  提示：输入 'demo' 仅运行演示，输入 'exit' 退出")
    print("="*60)

    # 为每次会话创建独立的 TaskCollector，确保隔离性
    collector = TaskCollector()

    async def on_task_update(task) -> None:
        """订阅任务状态变化，实时打印思考链。"""
        status_icon = {"DOING": "[Think]", "DONE": "[Done ]", "FAILED": "[FAIL ]"}.get(task.status.value, "[Wait ]")
        print(f"  {status_icon} [{task.status.value}] {task.tool_name}")
        if task.output and task.status.value == "DONE":
            print(f"     -> {task.output[:100]}")

    collector.subscribe(on_task_update)
    register_task_hook(collector)

    router = MainRouter()

    while True:
        user_input = input("\n[User]: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("再见！")
            break
        if not user_input:
            continue

        print()
        try:
            response = await router.route(user_input)
            print(f"\n[Agent]: {response.content}")
        except Exception as e:
            print(f"\n[Error]: {e}")
            print("提示：请确认 DASHSCOPE_API_KEY 环境变量已正确配置。")


async def main() -> None:
    """演示入口主函数。"""
    print("\n[START] AliGo 多智能体架构 - Python 实现演示")
    print("参考：阿里商旅基于 AgentScope 构建多智能体差旅助手最佳实践")
    print()

    # 运行无需 API Key 的功能演示
    demo_rule_engine()
    demo_dynamic_prompt()
    demo_state_machine()
    await demo_task_collector()

    # 仅在有有效 API Key 时才进入交互模式
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if api_key and api_key != "your_api_key_here":
        await interactive_mode()
    else:
        print("\n" + "="*60)
        print("  [INFO] 交互模式需要配置 DASHSCOPE_API_KEY 环境变量。")
        print("  演示模式展示完毕，以上均无需调用大模型 API。")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
