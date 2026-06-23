"""JSON 提取与序列化工具函数。

这个模块主要服务于大模型输出解析场景。
LLM 返回的内容并不总是严格的纯 JSON，常见情况包括：
1. 直接返回 JSON 对象；
2. 用 Markdown 代码块包裹 JSON；
3. 在 JSON 前后附带解释性文字。

这里提供的工具函数会尽量从文本中提取可解析的 JSON，
也会把 Python 对象安全地转换成字符串，方便写日志或传给下游处理。
"""

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """从文本中提取 JSON 对象。

    这个函数主要用于解析大模型返回内容。它按优先级处理三种情况：
    1. 文本为空：直接抛出错误；
    2. 文本中存在 ```json ... ``` 或 ``` ... ``` 代码块：优先解析代码块内容；
    3. 没有代码块：尝试截取第一个 { 到最后一个 } 之间的内容作为 JSON 解析。

    如果最终没有找到 JSON 对象，函数会抛出 ValueError，提醒调用方当前文本不可解析。
    """
    if not text:
        raise ValueError("empty text")

    # 优先解析 Markdown 代码块中的 JSON。
    # 很多 LLM 会把结构化结果包在 ```json ... ``` 中返回。
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return json.loads(fenced.group(1).strip())

    # 如果没有代码块，就尝试从普通文本中截取 JSON 对象。
    # 例如："下面是结果：{...}"，这种情况下可以取第一个 { 到最后一个 }。
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])

    # 没有找到任何 JSON 对象时，明确抛错，避免调用方误以为空结果是合法结果。
    raise ValueError("no JSON object found")


def stringify(value: Any) -> str:
    """将任意 Python 值转换为字符串。

    如果 value 本身已经是字符串，就直接返回；
    否则使用 json.dumps 转成 JSON 字符串。

    ensure_ascii=False 用来保留中文原文，不把中文转成 Unicode 转义；
    default=str 用来兜底处理 datetime、Path 等默认不能被 JSON 序列化的对象。
    """
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)
