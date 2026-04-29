"""
String Grep Strategy (Fallback)

When nothing else works — brute-force scan all smali files for
any const-string that looks like a GraphQL operation.
Works for custom GraphQL clients, OkHttp with raw strings, etc.
"""

import re
from pathlib import Path
from .base import BaseStrategy, parse_graphql_string


class StringGrepStrategy(BaseStrategy):
    name = "String Grep (fallback)"

    CONST_STRING_RE = re.compile(r'const-string(?:/jumbo)?\s+\w+,\s+"(.+)"')
    MIN_LENGTH = 40  # Minimum chars for a valid operation

    def extract(self) -> dict:
        smali_roots = [self.source / "smali"] + list(self.source.glob("smali_classes*"))
        smali_roots = [r for r in smali_roots if r.exists()]

        if not smali_roots:
            return {}

        operations_raw = set()

        for root in smali_roots:
            for smali_file in root.rglob("*.smali"):
                try:
                    content = smali_file.read_text(errors="ignore")
                    for m in self.CONST_STRING_RE.finditer(content):
                        s = self._unescape(m.group(1))
                        if self._looks_like_graphql(s):
                            operations_raw.add(s)
                except Exception:
                    pass

        self.log(f"Found {len(operations_raw)} GraphQL-looking strings")

        operations = []
        for raw in operations_raw:
            parsed = parse_graphql_string(raw)
            operations.extend(parsed)

        return {"operations": operations, "types": []}

    def _unescape(self, s: str) -> str:
        return s.replace("\\n", "\n").replace("\\t", "  ").replace('\\"', '"').replace("\\\\", "\\")

    def _looks_like_graphql(self, s: str) -> bool:
        s = s.strip()
        if len(s) < self.MIN_LENGTH:
            return False
        if not re.match(r'(?:query|mutation|subscription|fragment)\s+\w+', s, re.IGNORECASE):
            return False
        return "{" in s and "}" in s
