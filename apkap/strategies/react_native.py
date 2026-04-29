"""
React Native Strategy

React Native apps bundle JS into assets/index.android.bundle (or similar).
GraphQL operations are often visible as string literals in the bundle.

Also handles Relay (which uses __generated__ files).
"""

import re
import zipfile
from .base import BaseStrategy, parse_graphql_string


class ReactNativeStrategy(BaseStrategy):
    name = "React Native (JS bundle)"

    # Common bundle file paths in APK
    BUNDLE_PATHS = [
        "assets/index.android.bundle",
        "assets/index.bundle",
        "assets/main.jsbundle",
        "assets/app.bundle",
    ]

    # GraphQL operation regex in minified JS
    OPERATION_RE = re.compile(
        r'(?:query|mutation|subscription)\s+\w+[\s\(][^`"\']{10,}?\{[^}]{5,}?\}',
        re.DOTALL
    )
    
    # Template literal or string containing operation
    TEMPLATE_RE = re.compile(
        r'[`"\']((?:query|mutation|subscription)\s+\w+[\s\S]{20,}?)[`"\']',
    )

    def extract(self) -> dict:
        if not isinstance(self.source, zipfile.ZipFile):
            return {}

        bundle_content = None
        bundle_name = None

        # Try known bundle paths
        for path in self.BUNDLE_PATHS:
            try:
                bundle_content = self.source.read(path).decode("utf-8", errors="ignore")
                bundle_name = path
                break
            except (KeyError, Exception):
                pass

        # Also check for any .bundle or .jsbundle files
        if not bundle_content:
            for name in self.source.namelist():
                if name.endswith((".bundle", ".jsbundle")) and "assets" in name:
                    try:
                        bundle_content = self.source.read(name).decode("utf-8", errors="ignore")
                        bundle_name = name
                        break
                    except Exception:
                        pass

        if not bundle_content:
            self.log("No JS bundle found")
            return {}

        self.log(f"Found bundle: {bundle_name} ({len(bundle_content):,} bytes)")

        operations_raw = set()

        # Strategy 1: Template literals with full operations
        for m in self.TEMPLATE_RE.finditer(bundle_content):
            candidate = m.group(1).strip()
            if self._is_valid_operation(candidate):
                operations_raw.add(candidate)

        # Strategy 2: Relay persisted queries ({"id": "hash", "text": "query ..."})
        relay_re = re.compile(r'"text"\s*:\s*"((?:query|mutation|subscription)[^"]+)"')
        for m in relay_re.finditer(bundle_content):
            candidate = m.group(1).replace("\\n", "\n").replace('\\"', '"')
            if self._is_valid_operation(candidate):
                operations_raw.add(candidate)

        # Strategy 3: Apollo client with gql tag
        # gql`query GetUser { ... }` becomes gql("query GetUser { ... }")
        gql_re = re.compile(r'gql[(`"\']+(query|mutation|subscription)\s+\w+[\s\S]{10,}?[)`"\']')
        for m in gql_re.finditer(bundle_content):
            candidate = m.group(0)
            # Extract just the operation part
            inner = re.search(r'((?:query|mutation|subscription)\s+\w+[\s\S]+)', candidate)
            if inner:
                op = inner.group(1).rstrip('`"\')')
                if self._is_valid_operation(op):
                    operations_raw.add(op)

        self.log(f"Extracted {len(operations_raw)} operation candidates")

        operations = []
        for raw in operations_raw:
            parsed = parse_graphql_string(raw)
            operations.extend(parsed)

        return {"operations": operations, "types": []}

    def _is_valid_operation(self, text: str) -> bool:
        text = text.strip()
        if len(text) < 20:
            return False
        if not re.match(r'(?:query|mutation|subscription)\s+\w+', text, re.IGNORECASE):
            return False
        return "{" in text and "}" in text
