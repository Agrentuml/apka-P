"""
Apollo Kotlin Strategy

Apollo Kotlin compiles GraphQL operations into Kotlin/smali code.
The full operation document is stored as a string constant OPERATION_DOCUMENT.

Detection signals:
  - com/apollographql/ in smali class paths
  - Classes implementing com/apollographql/apollo3/api/Operation
  - String constants starting with 'query ', 'mutation ', 'subscription '

Extraction:
  1. Find OPERATION_DOCUMENT static fields → get full operation strings
  2. Find const-string values that are GraphQL operations (fallback)
  3. Parse operation strings with graphql-core
  4. Extract type info from InputAdapter classes
"""

import re
from pathlib import Path
from typing import Generator

from .base import BaseStrategy, parse_graphql_string


class ApolloKotlinStrategy(BaseStrategy):
    name = "Apollo Kotlin (smali)"

    # Regex to find const-string in smali
    CONST_STRING_RE = re.compile(r'const-string(?:/jumbo)?\s+\w+,\s+"(.+)"')
    
    # GraphQL operation start patterns
    OPERATION_START_RE = re.compile(r'^(query|mutation|subscription)\s+\w+', re.IGNORECASE)
    FRAGMENT_START_RE = re.compile(r'^fragment\s+\w+', re.IGNORECASE)
    
    # Apollo Kotlin class markers
    APOLLO_MARKERS = [
        "com/apollographql/",
        "apollo3/api/",
        "apollo/api/",
    ]

    def extract(self) -> dict:
        smali_root = self.source / "smali"
        if not smali_root.exists():
            # Some apktool versions use smali_classes2, smali_classes3, etc.
            smali_roots = list(self.source.glob("smali*"))
            if not smali_roots:
                return {}
        else:
            smali_roots = [smali_root] + list(self.source.glob("smali_classes*"))

        if not self._is_apollo_kotlin(smali_roots):
            self.log("No Apollo Kotlin markers found")
            return {}

        self.log("Apollo Kotlin detected, extracting operation documents...")

        operations_raw = set()
        fragments_raw = set()

        for root in smali_roots:
            for smali_file in root.rglob("*.smali"):
                for op, is_fragment in self._extract_from_smali(smali_file):
                    if is_fragment:
                        fragments_raw.add(op)
                    else:
                        operations_raw.add(op)

        self.log(f"Found {len(operations_raw)} operations, {len(fragments_raw)} fragments")

        # Combine: many Apollo Kotlin apps inline fragments in the operation string
        all_text = "\n\n".join(list(operations_raw) + list(fragments_raw))

        operations = []
        for raw in operations_raw:
            parsed = parse_graphql_string(raw)
            if parsed:
                operations.extend(parsed)

        # Extract input types from InputAdapter smali classes
        types = []
        for root in smali_roots:
            for smali_file in root.rglob("*InputAdapter.smali"):
                t = self._extract_input_type(smali_file)
                if t:
                    types.append(t)

        return {
            "operations": operations,
            "types": types,
            "raw_fragments": list(fragments_raw),
        }

    def _is_apollo_kotlin(self, smali_roots: list) -> bool:
        """Quick check: does this APK use Apollo Kotlin?"""
        for root in smali_roots:
            for marker in self.APOLLO_MARKERS:
                # Convert package path to directory structure
                marker_path = root / marker.replace("/", "/").rstrip("/")
                if marker_path.exists():
                    return True
            # Also check class content for Apollo imports
            for smali_file in list(root.rglob("*.smali"))[:200]:  # sample first 200
                try:
                    content = smali_file.read_text(errors="ignore")
                    if any(m in content for m in self.APOLLO_MARKERS):
                        return True
                except Exception:
                    pass
        return False

    def _extract_from_smali(self, path: Path) -> Generator[tuple[str, bool], None, None]:
        """Extract GraphQL operation strings from a smali file."""
        try:
            content = path.read_text(errors="ignore")
        except Exception:
            return

        # Strategy A: OPERATION_DOCUMENT pattern
        # In smali, this looks like a static field with the operation string
        if "OPERATION_DOCUMENT" in content or "operationDocument" in content:
            for match in self.CONST_STRING_RE.finditer(content):
                s = self._unescape_smali_string(match.group(1))
                if self._is_graphql_operation(s):
                    yield s, False
                elif self._is_graphql_fragment(s):
                    yield s, True
            return  # If file has OPERATION_DOCUMENT, trust it

        # Strategy B: Any const-string that looks like a GraphQL operation
        for match in self.CONST_STRING_RE.finditer(content):
            s = self._unescape_smali_string(match.group(1))
            if len(s) > 30:  # skip tiny strings
                if self._is_graphql_operation(s):
                    yield s, False
                elif self._is_graphql_fragment(s):
                    yield s, True

        # Strategy C: String concatenation builder (Apollo Kotlin sometimes splits long ops)
        combined = self._try_extract_string_builder(content)
        for s in combined:
            if self._is_graphql_operation(s):
                yield s, False

    def _unescape_smali_string(self, s: str) -> str:
        """Unescape smali string escapes to real GraphQL text."""
        return (s
            .replace("\\n", "\n")
            .replace("\\t", "  ")
            .replace("\\r", "")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )

    def _is_graphql_operation(self, s: str) -> bool:
        s = s.strip()
        return bool(self.OPERATION_START_RE.match(s)) and "{" in s

    def _is_graphql_fragment(self, s: str) -> bool:
        s = s.strip()
        return bool(self.FRAGMENT_START_RE.match(s)) and "{" in s

    def _try_extract_string_builder(self, content: str) -> list[str]:
        """
        Apollo Kotlin sometimes stores long operations as:
          new-instance v0, Ljava/lang/StringBuilder;
          const-string v1, "query SomeMutation("
          invoke-virtual {v0, v1}, ...append
          const-string v1, "$id: ID!"
          ...
        We try to reconstruct these.
        """
        results = []
        # Find blocks between StringBuilder instantiation and toString
        sb_blocks = re.split(r'new-instance \w+, Ljava/lang/StringBuilder;', content)
        for block in sb_blocks[1:]:
            # Get all const-strings appended before toString
            parts = []
            tostring_match = re.search(r'invoke-virtual.*StringBuilder.*toString', block)
            search_area = block[:tostring_match.start()] if tostring_match else block[:2000]
            
            for m in self.CONST_STRING_RE.finditer(search_area):
                parts.append(self._unescape_smali_string(m.group(1)))
            
            if parts:
                combined = "".join(parts)
                if self._is_graphql_operation(combined):
                    results.append(combined)
        return results

    def _extract_input_type(self, path: Path) -> dict | None:
        """Extract input type definition from an InputAdapter smali class."""
        try:
            content = path.read_text(errors="ignore")
        except Exception:
            return None

        # Get class name from .class directive
        class_match = re.search(r'\.class.*?L([\w/$]+)InputAdapter;', content)
        if not class_match:
            return None

        class_path = class_match.group(1)
        # The type name is the last part before InputAdapter
        parts = class_path.replace("$", "/").split("/")
        type_name = parts[-1] if parts else "Unknown"

        # Find field names from iput/iget operations or sput/sget
        fields = []
        # Look for string constants that look like field names (camelCase, short)
        field_name_re = re.compile(r'const-string(?:/jumbo)?\s+\w+,\s+"([a-z][a-zA-Z0-9_]+)"')
        for m in field_name_re.finditer(content):
            name = m.group(1)
            if 2 < len(name) < 50 and not name.startswith("__"):
                fields.append({"name": name, "type": "String"})  # type unknown from smali

        # Also look for .field directives
        for m in re.finditer(r'\.field.*?(\w+):([A-Za-z/;$\[\w]+)', content):
            fname = m.group(1)
            if not fname.startswith("$") and len(fname) > 1:
                fields.append({"name": fname, "type": "Unknown"})

        if not fields:
            return None

        # Deduplicate
        seen = set()
        unique_fields = []
        for f in fields:
            if f["name"] not in seen:
                seen.add(f["name"])
                unique_fields.append(f)

        return {
            "name": type_name,
            "kind": "INPUT_OBJECT",
            "fields": unique_fields,
            "source": "InputAdapter",
        }
