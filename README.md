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
