# -*- coding: utf-8 -*-
"""
实时思考链 Hook 与 TaskCollector
==================================
设计思路：
  引入多智能体架构后，响应总延迟明显增加。AliGo 的解法是：通过 AgentScope 的
  Hook 机制拦截 ReActAgent 的每次工具调用（tool_use / tool_result），
  将思考过程实时分发给 TaskCollector —— 一个发布-订阅模式的状态机，
  再由外部消费者（如 FastAPI SSE 接口）按订阅顺序推送给前端，
  实现"思考链" (Chain-of-Thought) 的实时可视化。

设计亮点：
  1. 非侵入式注入：借助 AgentScope 的 register_class_hook，无需修改 ReActAgent
     的核心逻辑，只添加一个独立的 hook 函数，完全符合开闭原则。
  2. 发布-订阅解耦：TaskCollector 是独立的状态容器，与具体的 Agent 实现无关，
     任何消费者都可以通过 subscribe()/unsubscribe() 接入或退出，
     天然支持多个订阅者（如日志系统、SSE 流式接口）。
  3. 生命周期管理：每个工具调用对应一个 Task 对象（PENDING→DOING→DONE/FAILED），
     提供完整的状态追踪，方便后接观测平台（Langfuse 等）使用。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from agentscope.agent import ReActAgent
from agentscope.message import Msg


# -----------------------------------------------------------------------
# 任务状态枚举
# -----------------------------------------------------------------------
class TaskStatus(str, Enum):
    """工具调用任务的生命周期状态。

    对应 AliGo 文章中描述的 PENDING、DOING、DONE、FAILED 四态。
    """
    PENDING = "PENDING"
    DOING = "DOING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class Task:
    """单次工具调用的任务状态容器。

    Attributes:
        task_id (str): 该任务的唯一标识，与工具调用 ID 对齐。
        tool_name (str): 被调用工具的名称，用于在思考链 UI 中显示标题。
        tool_input (dict): 工具的输入参数。
        status (TaskStatus): 当前任务状态。
        output (str | None): 工具执行结果，DONE 状态后更新。
        parent_id (str | None): 父任务 ID，用于维护嵌套的层级关系。
    """
    task_id: str
    tool_name: str
    tool_input: dict
    status: TaskStatus = TaskStatus.PENDING
    output: str | None = None
    parent_id: str | None = None


# 异步回调类型：接受一个更新后的 Task 对象
SubscriberCallback = Callable[[Task], Coroutine[Any, Any, None]]


class TaskCollector:
    """实时思考链状态收集器（发布-订阅模式）。
    
    职责：
        统一管理工具调用的完整生命周期，并在状态变更时实时通知所有订阅者。
        是连接 ReActAgent Hook 和外部流式接口的桥梁。
    """

    def __init__(self) -> None:
        """初始化 TaskCollector，创建任务和订阅者的空容器。"""
        self._tasks: dict[str, Task] = {}
        self._subscribers: list[SubscriberCallback] = []
        self._task_stack: list[str] = []  # 用出入栈方式维护调用层级

    def subscribe(self, callback: SubscriberCallback) -> None:
        """注册一个订阅者回调函数。

        Args:
            callback (SubscriberCallback): 接受 Task 对象的异步回调。
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: SubscriberCallback) -> None:
        """注销一个订阅者回调函数。

        Args:
            callback (SubscriberCallback): 要注销的回调引用。
        """
        self._subscribers = [s for s in self._subscribers if s is not callback]

    async def _notify(self, task: Task) -> None:
        """内部方法：向全部订阅者广播最新任务状态。

        Args:
            task (Task): 状态发生变化的任务对象。
        """
        await asyncio.gather(*[cb(task) for cb in self._subscribers])

    async def add_tool_use(self, tool_id: str, tool_name: str, tool_input: dict) -> None:
        """记录一次工具调用的开始（对应 tool_use 消息）。

        将任务状态初始化为 DOING，推入调用栈，并通知订阅者。

        Args:
            tool_id (str): AgentScope 生成的工具调用唯一 ID。
            tool_name (str): 工具名称。
            tool_input (dict): 工具输入参数。
        """
        parent_id = self._task_stack[-1] if self._task_stack else None
        task = Task(
            task_id=tool_id,
            tool_name=tool_name,
            tool_input=tool_input,
            status=TaskStatus.DOING,
            parent_id=parent_id,
        )
        self._tasks[tool_id] = task
        self._task_stack.append(tool_id)
        await self._notify(task)

    async def add_tool_result(self, tool_id: str, output: str, success: bool = True) -> None:
        """记录一次工具调用的结果（对应 tool_result 消息）。

        将任务状态更新为 DONE 或 FAILED，弹出调用栈，并通知订阅者。

        Args:
            tool_id (str): 对应 add_tool_use 中的工具调用 ID。
            output (str): 工具执行的文本结果。
            success (bool): 是否执行成功，默认为 True。
        """
        task = self._tasks.get(tool_id)
        if task is None:
            return
        task.output = output
        task.status = TaskStatus.DONE if success else TaskStatus.FAILED
        # 弹出调用栈
        if tool_id in self._task_stack:
            self._task_stack.remove(tool_id)
        await self._notify(task)


# -----------------------------------------------------------------------
# AgentScope Print Hook：非侵入式拦截 ReActAgent 的工具调用输出
# -----------------------------------------------------------------------
def build_task_print_hook(collector: TaskCollector):
    """工厂函数：返回一个绑定了特定 TaskCollector 实例的 Hook 函数。

    设计原因：
        Hook 函数需要闭包捕获同一个 collector 实例，
        使用工厂函数可以灵活地为不同请求创建独立的 collector 上下文，
        互不干扰（每次对话请求创建一个新的 collector）。

    Args:
        collector (TaskCollector): 本次请求关联的任务收集器实例。

    Returns:
        Callable: 符合 AgentScope pre_print_hook 签名的异步函数。
    """
    async def task_print_hook(agent: ReActAgent, msg: Msg, *args, **kwargs) -> Msg:
        """前置打印钩子：拦截 AgentScope 消息并通知 TaskCollector。

        当 AgentScope 调用 agent.print() 之前，此 hook 会被触发。
        通过检查消息内容块的类型，区分工具调用（tool_use）和工具结果（tool_result）。

        Args:
            agent (ReActAgent): 触发打印的 Agent 实例。
            msg (Msg): 即将被打印的消息对象。
        """
        if not msg.content or not isinstance(msg.content, list):
            return msg

        block = msg.content[0] if msg.content else {}
        block_type = block.get("type", "") if isinstance(block, dict) else ""

        if block_type == "tool_use":
            # 工具调用开始
            await collector.add_tool_use(
                tool_id=block.get("id", str(uuid.uuid4())),
                tool_name=block.get("name", "unknown_tool"),
                tool_input=block.get("input", {}),
            )
        elif block_type == "tool_result":
            # 工具执行完成
            output_content = block.get("output", [])
            output_text = ""
            if isinstance(output_content, list) and output_content:
                output_text = output_content[0].get("text", "") if isinstance(output_content[0], dict) else str(output_content[0])
            await collector.add_tool_result(
                tool_id=block.get("id", ""),
                output=output_text,
                success=True,
            )

        # 同时打印到终端，便于本地调试
        print(f"[HOOK] {block_type} | {block.get('name', '')} => {str(block)[:120]}")
        return msg

    return task_print_hook


def register_task_hook(collector: TaskCollector) -> None:
    """将 task_print_hook 注册到 ReActAgent 的类级别 print hook 上。

    设计原因：
        AgentScope 的 register_class_hook 作用于类的所有实例，
        对所有 ReActAgent 对象统一生效，所以只需调用一次即可覆盖全链路。

    Args:
        collector (TaskCollector): 用于广播工具调用状态的收集器实例。
    """
    hook_fn = build_task_print_hook(collector)
    ReActAgent.register_class_hook("print", "task_print_hook", hook_fn)
