# AgentScope 代码评审规范

你需要进行**严格的代码评审**。每一项要求都带有优先级标识：

* **[MUST]**：必须满足，否则 PR 将被拒绝
* **[SHOULD]**：强烈建议遵循
* **[MAY]**：可选建议

---

## 1. 代码质量

### [MUST] 延迟加载（Lazy Loading）

* 第三方库依赖必须在**实际使用的位置导入**，避免在文件顶部集中导入

  * 这里的「第三方库」指的是**未包含在 `pyproject.toml` 的 `dependencies` 变量中的库**
* 对于基类的导入，必须使用**工厂模式**：

```python
def get_xxx_cls() -> "MyClass":
    from xxx import BaseClass
    class MyClass(BaseClass): ...
    return MyClass
```

---

### [SHOULD] 代码简洁性

在理解代码意图之后，检查是否可以进行优化：

* 避免不必要的临时变量
* 合并重复的代码块
* 优先复用已有的工具函数

---

### [MUST] 封装规范

* `src/bluehelm` 目录下的所有 Python 文件，**必须以下划线 `_` 开头命名**，并通过 `__init__.py` 控制对外暴露
* 框架内部使用、且**不需要对用户暴露**的类和函数，必须以下划线 `_` 作为前缀命名

---

## 2. [MUST] 代码安全

* **禁止**硬编码 API Key / Token / 密码
* 必须使用**环境变量或配置文件**进行管理
* 检查是否存在调试信息或临时凭证
* 检查是否存在注入攻击风险（如 SQL / 命令 / 代码注入等）

---

## 3. [MUST] 测试与依赖管理

* 新增功能**必须包含单元测试**
* 新增依赖**必须添加到 `pyproject.toml` 中对应的依赖区块**
* 非核心场景的依赖**不得**加入最小依赖列表（minimal dependencies）

---

## 4. 代码规范

### [MUST] 注释规范

* **统一使用英文**
* 所有类和方法**必须**包含完整的 docstring，并且**严格遵循以下模板**：

```python
def func(a: str, b: int | None = None) -> str:
    """{description}

    Args:
        a (`str`):
            参数 a
        b (`int | None`, optional):
            参数 b

    Returns:
        `str`:
            返回值
    """
```

* 特殊内容必须使用 **reStructuredText** 语法：

```python
class MyClass:
    """xxx

    `示例链接 <https://xxx>`_

    .. note:: 示例说明

    .. tip:: 示例提示

    .. important:: 示例重要信息

    .. code-block:: python

        def hello_world():
            print("Hello world!")

    """
```

---

### [MUST] Pre-commit 检查

* **严格执行代码审查**：大多数情况下，应修改代码而不是跳过检查
* **禁止跳过文件级别的检查**
* 唯一允许跳过的情况：

  * agent 类中的 system prompt 参数（用于避免 `\n` 格式化问题）

---

## 5. Git 规范

### [MUST] PR 标题规范

* 遵循 **Conventional Commits** 规范
* 必须使用以下前缀之一：`feat / fix / docs / ci / refactor / test` 等
* 格式要求：`feat(scope): description`
* 示例：

```
feat(memory): add redis cache support
```

