import json
from typing import Any

import httpx

from kg_agent.ports import ExtractedFact


class DeepSeekFactExtractor:
    ENDPOINT = "https://api.deepseek.com/chat/completions"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-flash",
        timeout_seconds: float = 90.0,
    ) -> None:
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract(self, text: str) -> list[ExtractedFact]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": f"请从以下原文抽取事实并输出 json：\n\n{text}"},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 4096,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                self.ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"].get("content")
        if not content or not content.strip():
            raise RuntimeError("DeepSeek returned empty JSON content")
        parsed = json.loads(content)
        facts = parsed.get("facts", [])
        if not isinstance(facts, list):
            raise ValueError("DeepSeek JSON must contain a facts array")
        return [self._parse_fact(item) for item in facts[:50]]

    @staticmethod
    def _parse_fact(item: Any) -> ExtractedFact:
        if not isinstance(item, dict):
            raise ValueError("Each extracted fact must be a JSON object")
        return ExtractedFact(
            source_type=str(item["source_type"]),
            source_name=str(item["source_name"]),
            predicate=str(item["predicate"]),
            target_type=str(item["target_type"]),
            target_name=str(item["target_name"]),
            evidence_quote=str(item["evidence_quote"]),
            confidence=float(item["confidence"]),
        )

    @staticmethod
    def _system_prompt() -> str:
        return """
你是一个严格的知识图谱事实抽取器。只能抽取原文明确支持的事实，输出合法 json。

实体类型只能是：Person, Project, Component, Technology, Decision, Document。
关系只能是：OWNS, PART_OF, DEPENDS_ON, USES, DECIDED_BY, AFFECTS, DOCUMENTED_IN。
evidence_quote 必须逐字复制自原文，禁止改写；找不到直接证据就不要输出。
confidence 是 0 到 1 的数字。不要输出解释或 Markdown。

JSON 格式示例：
{
  "facts": [
    {
      "source_type": "Project",
      "source_name": "知识图谱 Agent",
      "predicate": "USES",
      "target_type": "Technology",
      "target_name": "DeepSeek",
      "evidence_quote": "知识图谱 Agent 使用 DeepSeek 抽取实体关系。",
      "confidence": 0.95
    }
  ]
}
没有可抽取事实时返回 {"facts": []}。
""".strip()


class UnavailableFactExtractor:
    def extract(self, text: str) -> list[ExtractedFact]:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

