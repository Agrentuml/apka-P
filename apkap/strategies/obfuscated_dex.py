"""
Obfuscated DEX Strategy

Reads DEX string pool directly from binary — bypasses class name obfuscation.

Extracts:
  - GraphQL operations (query/mutation/subscription strings)
  - Input types (by parsing field patterns around Input/Request/Params strings)
  - Enum values (ALL_CAPS_WITH_UNDERSCORES clusters)
"""

import struct
import zipfile
import re
from collections import defaultdict
from .base import BaseStrategy, parse_graphql_string


class ObfuscatedDexStrategy(BaseStrategy):
    name = "Obfuscated DEX (direct string pool)"

    DEX_MAGIC   = b"dex\n"
    MIN_OP_LEN  = 35
    MIN_STR_LEN = 2

    # Type name patterns: PascalCase, ends with Input/Response/Payload/Result/Type etc.
    INPUT_TYPE_RE  = re.compile(r'^[A-Z][a-zA-Z0-9]*(Input|Request|Params|Payload|Args|Data)$')
    OBJECT_TYPE_RE = re.compile(r'^[A-Z][a-zA-Z0-9]*(Response|Result|Payload|Type|Info|Detail|Summary|Node|Edge|Connection)$')
    # Field name pattern: camelCase, 2-40 chars
    FIELD_NAME_RE  = re.compile(r'^[a-z][a-zA-Z0-9]{1,39}$')
    # Enum values: UPPER_SNAKE_CASE
    ENUM_VAL_RE    = re.compile(r'^[A-Z][A-Z0-9_]{2,39}$')

    def extract(self) -> dict:
        if not isinstance(self.source, zipfile.ZipFile):
            return {}

        dex_files = sorted(
            n for n in self.source.namelist()
            if re.match(r"classes\d*\.dex", n)
        )
        if not dex_files:
            return {}

        self.log(f"DEX files: {dex_files}")

        all_strings = []
        for dex_name in dex_files:
            try:
                data = self.source.read(dex_name)
                strings = self._extract_strings(data)
                self.log(f"{dex_name}: {len(strings):,} strings")
                all_strings.extend(strings)
            except Exception as e:
                self.log(f"Failed {dex_name}: {e}")

        # ── Operations ───────────────────────────────────────────────
        op_strings = [s for s in all_strings if self._is_graphql_op(s)]
        self.log(f"GraphQL operations: {len(op_strings)}")

        operations = []
        for raw in set(op_strings):
            operations.extend(parse_graphql_string(raw))

        # ── Types from string context ────────────────────────────────
        types = self._infer_types(all_strings, operations)
        self.log(f"Types inferred: {len(types)}")

        return {"operations": operations, "types": types}

    # ── Type inference ───────────────────────────────────────────────

    def _infer_types(self, strings: list[str], operations: list[dict]) -> list[dict]:
        """
        Infer type definitions from:
        1. Variable types declared in operations ($input: CreateReservationInput!)
        2. String pool patterns — type name followed by field names
        3. Enum clusters (consecutive UPPER_SNAKE strings near a type name)
        """
        types = {}

        # 1. Collect known type names from operation variables
        known_input_types = set()
        for op in operations:
            for var in op.get("variables", []):
                t = var.get("type", "").strip("![]")
                if t and t[0].isupper() and t not in ("String", "Int", "Float", "Boolean", "ID"):
                    known_input_types.add(t)

        # 2. Scan string pool for type-name → field-name sequences
        #    Apollo Kotlin stores these as consecutive strings in the pool
        field_names = [s for s in strings if self.FIELD_NAME_RE.match(s)]
        type_names  = [s for s in strings if self._is_type_name(s)]

        # Build adjacency: which field names appear near which type names
        # Use a sliding window over the string pool
        str_index = {s: i for i, s in enumerate(strings)}

        for tname in type_names:
            if tname not in str_index:
                continue
            idx = str_index[tname]
            # Look at ±30 strings around the type name
            window = strings[max(0, idx-5) : idx+30]
            fields = [
                {"name": s, "type": "Unknown"}
                for s in window
                if self.FIELD_NAME_RE.match(s) and s != tname
            ]
            # Deduplicate
            seen = set()
            unique_fields = []
            for f in fields:
                if f["name"] not in seen:
                    seen.add(f["name"])
                    unique_fields.append(f)

            if len(unique_fields) >= 2:
                kind = "INPUT_OBJECT" if self.INPUT_TYPE_RE.match(tname) else "OBJECT"
                if tname not in types:
                    types[tname] = {
                        "name": tname,
                        "kind": kind,
                        "fields": unique_fields,
                        "source": "DEX inference",
                    }

        # 3. Known input types from operations — ensure they're in types dict
        for tname in known_input_types:
            if tname not in types:
                types[tname] = {
                    "name": tname,
                    "kind": "INPUT_OBJECT",
                    "fields": [],
                    "source": "operation variable",
                }

        # 4. Enum detection — clusters of UPPER_SNAKE_CASE strings
        enums = self._detect_enums(strings, type_names)
        for enum in enums:
            if enum["name"] not in types:
                types[enum["name"]] = enum

        return list(types.values())

    def _detect_enums(self, strings: list[str], type_names: list[str]) -> list[dict]:
        """Find enum types: PascalCase name followed by UPPER_SNAKE values."""
        enums = []
        type_name_set = set(type_names)
        i = 0
        while i < len(strings):
            s = strings[i]
            if s in type_name_set and re.match(r'^[A-Z][a-zA-Z0-9]+$', s):
                # Look ahead for UPPER_SNAKE values
                values = []
                j = i + 1
                while j < min(i + 25, len(strings)):
                    candidate = strings[j]
                    if self.ENUM_VAL_RE.match(candidate):
                        values.append({"name": candidate, "type": "EnumValue"})
                    elif len(values) > 0 and not self.ENUM_VAL_RE.match(candidate):
                        break
                    j += 1
                if len(values) >= 2:
                    enums.append({
                        "name": s,
                        "kind": "ENUM",
                        "fields": values,
                        "source": "DEX enum detection",
                    })
            i += 1
        return enums

    def _is_type_name(self, s: str) -> bool:
        return bool(
            self.INPUT_TYPE_RE.match(s) or
            self.OBJECT_TYPE_RE.match(s) or
            re.match(r'^[A-Z][a-zA-Z0-9]{3,40}$', s)
        )

    # ── DEX binary parser ────────────────────────────────────────────

    def _extract_strings(self, data: bytes) -> list[str]:
        if data[:4] != self.DEX_MAGIC or len(data) < 112:
            return []
        try:
            string_ids_size = struct.unpack_from("<I", data, 56)[0]
            string_ids_off  = struct.unpack_from("<I", data, 60)[0]
        except struct.error:
            return []

        if string_ids_size > 5_000_000 or string_ids_off > len(data):
            return []

        strings = []
        for i in range(string_ids_size):
            id_off = string_ids_off + i * 4
            if id_off + 4 > len(data):
                break
            str_data_off = struct.unpack_from("<I", data, id_off)[0]
            if str_data_off >= len(data):
                continue
            try:
                utf16_len, content_start = self._read_uleb128(data, str_data_off)
                if utf16_len < self.MIN_STR_LEN or utf16_len > 50_000:
                    continue
                content_end = content_start + utf16_len
                if content_end > len(data):
                    continue
                s = data[content_start:content_end].decode("utf-8", errors="ignore")
                strings.append(s)
            except Exception:
                continue
        return strings

    def _read_uleb128(self, data: bytes, offset: int) -> tuple[int, int]:
        result, shift = 0, 0
        while offset < len(data):
            byte = data[offset]; offset += 1
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return result, offset

    def _is_graphql_op(self, s: str) -> bool:
        s = s.strip()
        return (
            len(s) >= self.MIN_OP_LEN and
            bool(re.match(r"(?:query|mutation|subscription)\s+\w+", s, re.IGNORECASE)) and
            "{" in s and "}" in s
        )
