"""
安全防护模块

提供 Prompt Injection 检测、敏感信息脱敏、权限校验等安全功能。
"""

import re
from typing import Any, Optional

import structlog

from src.config import get_settings

logger = structlog.get_logger()


# Prompt Injection 检测模式
INJECTION_PATTERNS = [
    # 系统提示词覆盖
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"new\s+system\s+prompt",
    r"new\s+instructions",
    r"you\s+are\s+now",
    r"act\s+as\s+if",
    r"pretend\s+you\s+are",
    r"roleplay\s+as",

    # 角色劫持
    r"you\s+are\s+no\s+longer",
    r"stop\s+being",
    r"change\s+your\s+role",
    r"switch\s+to\s+mode",

    # 信息泄露
    r"reveal\s+(your|the)\s+(system|prompt|instructions)",
    r"show\s+me\s+(your|the)\s+(system|prompt|instructions)",
    r"what\s+(is|are)\s+(your|the)\s+(system|prompt|instructions)",
    r"repeat\s+(your|the)\s+(system|prompt|instructions)",
    r"print\s+(your|the)\s+(system|prompt|instructions)",

    # 越狱尝试
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode",
    r"bypass\s+(safety|content|filter)",
    r"without\s+restrictions",
    r"no\s+restrictions",
    r"no\s+limits",
    r"no\s+rules",
    r"no\s+guidelines",

    # 恶意指令
    r"execute\s+code",
    r"run\s+code",
    r"eval\s*\(",
    r"exec\s*\(",
    r"import\s+os",
    r"subprocess",
    r"__import__",
]

# 编译正则表达式
INJECTION_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS]

# 敏感信息模式
SENSITIVE_PATTERNS = {
    "phone": re.compile(r"1[3-9]\d{9}"),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "id_card": re.compile(r"\d{17}[\dXx]"),
    "credit_card": re.compile(r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}"),
    "bank_account": re.compile(r"\d{16,19}"),
}


class InjectionDetector:
    """
    Prompt Injection 检测器

    检测用户输入中是否包含 Prompt Injection 攻击。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def detect(self, text: str) -> dict[str, Any]:
        """
        检测 Prompt Injection

        Args:
            text: 用户输入文本

        Returns:
            检测结果，包含是否检测到注入和匹配的模式
        """
        if not self.settings.security.enable_injection_detection:
            return {"detected": False, "patterns": []}

        detected_patterns = []

        for pattern in INJECTION_REGEX:
            match = pattern.search(text)
            if match:
                detected_patterns.append({
                    "pattern": pattern.pattern,
                    "match": match.group(),
                    "position": match.span(),
                })

        return {
            "detected": len(detected_patterns) > 0,
            "patterns": detected_patterns,
            "risk_level": "high" if len(detected_patterns) >= 2 else "medium" if detected_patterns else "low",
        }


class SensitiveDataMasker:
    """
    敏感信息脱敏器

    对敏感信息进行脱敏处理，防止泄露。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def mask(self, text: str, mask_char: str = "*") -> str:
        """
        对文本中的敏感信息进行脱敏

        Args:
            text: 原始文本
            mask_char: 脱敏字符

        Returns:
            脱敏后的文本
        """
        masked_text = text

        for field_name in self.settings.security.sensitive_fields:
            pattern = SENSITIVE_PATTERNS.get(field_name)
            if pattern:
                masked_text = pattern.sub(
                    lambda m: self._mask_match(m.group(), mask_char),
                    masked_text,
                )

        return masked_text

    def _mask_match(self, match: str, mask_char: str) -> str:
        """对匹配到的内容进行脱敏"""
        if len(match) <= 4:
            return mask_char * len(match)

        # 保留前 3 位和后 4 位
        return match[:3] + mask_char * (len(match) - 7) + match[-4:]

    def mask_dict(self, data: dict[str, Any], fields: Optional[list[str]] = None) -> dict[str, Any]:
        """
        对字典中的敏感字段进行脱敏

        Args:
            data: 原始数据
            fields: 需要脱敏的字段列表（默认使用配置）

        Returns:
            脱敏后的数据
        """
        if fields is None:
            fields = self.settings.security.sensitive_fields

        masked_data = {}
        for key, value in data.items():
            if key in fields and isinstance(value, str):
                masked_data[key] = self.mask(value)
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dict(value, fields)
            elif isinstance(value, list):
                masked_data[key] = [
                    self.mask_dict(item, fields) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked_data[key] = value

        return masked_data


class Guardrails:
    """
    安全防护综合类

    整合所有安全防护功能。
    """

    def __init__(self) -> None:
        self.injection_detector = InjectionDetector()
        self.data_masker = SensitiveDataMasker()

    def check_input(self, user_input: str) -> dict[str, Any]:
        """
        检查用户输入

        Args:
            user_input: 用户输入

        Returns:
            检查结果
        """
        # 检测 Prompt Injection
        injection_result = self.injection_detector.detect(user_input)

        return {
            "safe": not injection_result["detected"],
            "injection": injection_result,
        }

    def mask_output(self, output: str) -> str:
        """
        对输出进行脱敏

        Args:
            output: 原始输出

        Returns:
            脱敏后的输出
        """
        return self.data_masker.mask(output)

    def mask_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        对数据进行脱敏

        Args:
            data: 原始数据

        Returns:
            脱敏后的数据
        """
        return self.data_masker.mask_dict(data)


# 全局安全防护实例
guardrails = Guardrails()
