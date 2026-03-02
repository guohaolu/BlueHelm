# BlueHelm
舵手，AI Agent 服务

## 项目简介
本项目基于 Python 3.11 + uv 工具开发，并使用 AgentScope 框架进行一次 Agent 的开发。

## 快速开始

### 1. 安装依赖
```bash
uv add agentscope
```

### 2. 运行示例 Agent
本项目包含了一个基础的具备 ReAct 逻辑与工具调用能力的 Agent `BlueHelm_Assistant`。该代理使用了 DashScope 的 `qwen-max` 大语言模型。

运行之前，请确保你已经设置了环境变量并赋予相应权限：
```bash
# Windows(PowerShell)
$env:DASHSCOPE_API_KEY="your_api_key_here"

# Linux/macOS
export DASHSCOPE_API_KEY="your_api_key_here"
```

进入对话交互界面：
```bash
uv run src/main.py
```

### 3. 测试
所有的业务逻辑包含单元测试，通过标准库 `unittest` 驱动：
```bash
uv run python -m unittest discover -s tests
```

---

## AliGo 风格多智能体架构

本项目内置了一套参考[阿里商旅 AliGo 最佳实践](assert/准确率提升至%2090%25，阿里商旅基于%20AgentScope%20构建多智能体差旅助手最佳实践.md)的多智能体差旅助手演示，将事项收集准确率从 50% 提升至 90%+ 的核心工程方法落地为可运行代码。

### 核心设计亮点

| 模块 | 对应特性 | 设计亮点 |
|---|---|---|
| `src/classifiers/rule_engine.py` | **快慢车道意图识别** | `IntentType` 枚举令牌化路由，关键词+正则双层匹配，命中时零 LLM 成本 |
| `src/agents/aligo_agents/hooks.py` | **实时思考链追踪** | `TaskCollector` 发布-订阅模式 + AgentScope `register_class_hook` 非侵入式拦截工具调用 |
| `src/agents/aligo_agents/main_router.py` | **动态 Prompt 生成** | Prompt 工厂函数为纯函数，Python 层负责控流（确定性），LLM 负责语义（灵活性） |
| `src/agents/aligo_agents/dynamic_prompt.py` | **Prompt 状态机** | `CollectState` dataclass 封装阶段数据，S1/S2/S3 各有独立精简 Prompt，LLM 注意力高度集中 |
| `src/agents/aligo_agents/sub_agents.py` | **多 Agent 路由** | `TripPlanAgent` / `InfoQueryAgent` 各司其职，独立记忆隔离，支持按需记忆共享 |

### 运行 AliGo 演示

**演示模式（无需 API KEY，快车道/状态机/思考链追踪均可直接验证）：**
```bash
# Windows PowerShell
$env:PYTHONIOENCODING="utf-8"; uv run python src/aligo_demo.py
```

**交互模式（需配置 DASHSCOPE_API_KEY，开启完整慢车道 LLM 分析和子 Agent 对话）：**
```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY="your_api_key_here"
$env:PYTHONIOENCODING="utf-8"; uv run python src/aligo_demo.py
```

### 项目模块结构

```
src/
├── classifiers/
│   └── rule_engine.py          # 意图识别快车道（规则引擎）
├── agents/
│   ├── react_agent.py          # 基础 ReAct Agent 工厂
│   └── aligo_agents/
│       ├── hooks.py            # TaskCollector + ReActAgent print Hook
│       ├── sub_agents.py       # 行程规划 / 政策查询 子 Agent
│       ├── main_router.py      # 主路由器（快慢车道 + 动态 Prompt）
│       └── dynamic_prompt.py   # 事项收集 Prompt 状态机（S1/S2/S3）
├── tools/
│   └── basic_tools.py          # 基础工具（时间 / 天气）
├── main.py                     # 基础 ReAct Agent 交互入口
└── aligo_demo.py               # AliGo 多智能体架构演示入口
tests/
├── test_tools.py               # 工具层单元测试
└── test_agent.py               # Agent 工厂单元测试
```
