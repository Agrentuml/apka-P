"""
apka-P test suite
Run: pytest tests/ -v
"""

import json
import struct
import zipfile
import tempfile
from pathlib import Path
import pytest

from apkap.strategies.base import parse_graphql_string
from apkap.strategies.assets_graphql import AssetsGraphQLStrategy
from apkap.strategies.obfuscated_dex import ObfuscatedDexStrategy
from apkap.strategies.react_native import ReactNativeStrategy
from apkap.reporters.json_reporter import write_json
from apkap.extractor import Extractor


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_apk(files: dict) -> Path:
    """Create a temp APK (zip) with given filename→content pairs."""
    tmp = tempfile.NamedTemporaryFile(suffix=".apk", delete=False)
    with zipfile.ZipFile(tmp.name, "w") as z:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode()
            z.writestr(name, content)
    return Path(tmp.name)


def build_dex(strings: list[str]) -> bytes:
    """Build a minimal valid DEX with the given strings in the string pool."""
    def write_uleb128(v):
        r = []
        while True:
            b = v & 0x7F; v >>= 7
            if v: b |= 0x80
            r.append(b)
            if not v: break
        return bytes(r)

    items = []
    for s in strings:
        enc = s.encode("utf-8")
        items.append(write_uleb128(len(s)) + enc + b"\x00")

    n = len(strings)
    header_size    = 0x70
    string_ids_off = header_size
    string_data_base = header_size + n * 4
    if string_data_base % 4:
        string_data_base += 4 - string_data_base % 4

    offsets = []
    pos = string_data_base
    for item in items:
        offsets.append(pos); pos += len(item)

    total_size = string_data_base + sum(len(i) for i in items)
    header = bytearray(0x70)
    header[:8] = b"dex\n035\x00"
    struct.pack_into("<I", header, 32, total_size)
    struct.pack_into("<I", header, 36, 0x70)
    struct.pack_into("<I", header, 40, 0x12345678)
    struct.pack_into("<I", header, 56, n)
    struct.pack_into("<I", header, 60, string_ids_off)

    ids_section = b"".join(struct.pack("<I", o) for o in offsets)
    padding     = b"\x00" * (string_data_base - header_size - n * 4)
    data_section = b"".join(items)
    return bytes(header) + ids_section + padding + data_section


# ── parse_graphql_string ──────────────────────────────────────────────────────

class TestParseGraphqlString:
    def test_simple_query(self):
        raw = "query GetUser($id: ID!) { user(id: $id) { id email } }"
        result = parse_graphql_string(raw)
        assert len(result) == 1
        assert result[0]["name"] == "GetUser"
        assert result[0]["type"] == "query"

    def test_mutation(self):
        raw = "mutation DeleteAccount($userId: ID!) { deleteAccount(userId: $userId) { success } }"
        result = parse_graphql_string(raw)
        assert result[0]["type"] == "mutation"
        assert result[0]["name"] == "DeleteAccount"

    def test_subscription(self):
        raw = "subscription OnMessage($id: ID!) { newMessage(id: $id) { content } }"
        result = parse_graphql_string(raw)
        assert result[0]["type"] == "subscription"

    def test_variables_parsed(self):
        raw = "mutation Update($id: ID!, $name: String) { update(id: $id, name: $name) { id } }"
        result = parse_graphql_string(raw)
        vars_ = result[0]["variables"]
        names = [v["name"] for v in vars_]
        assert "id" in names
        assert "name" in names

    def test_required_flag(self):
        raw = "mutation M($a: ID!, $b: String) { m(a: $a) { id } }"
        result = parse_graphql_string(raw)
        vars_ = {v["name"]: v for v in result[0]["variables"]}
        assert vars_["a"]["type"].endswith("!")
        assert not vars_["b"]["type"].endswith("!")

    def test_empty_string(self):
        assert parse_graphql_string("") == []

    def test_non_graphql(self):
        assert parse_graphql_string("hello world") == []

    def test_multiple_operations(self):
        raw = """
        query A { a { id } }
        mutation B($x: ID!) { b(x: $x) { ok } }
        """
        result = parse_graphql_string(raw)
        assert len(result) == 2


# ── AssetsGraphQLStrategy ─────────────────────────────────────────────────────

class TestAssetsGraphQLStrategy:
    def test_finds_graphql_files(self):
        apk = make_apk({
            "assets/GetUser.graphql": "query GetUser($id: ID!) { user(id: $id) { id email } }",
            "assets/UpdateProfile.graphql": "mutation UpdateProfile($id: ID!) { update(id: $id) { id } }",
            "AndroidManifest.xml": "<manifest/>",
        })
        with zipfile.ZipFile(apk) as z:
            result = AssetsGraphQLStrategy(z).extract()
        assert len(result["operations"]) == 2

    def test_finds_schema_json(self):
        schema = {
            "data": {"__schema": {"types": [
                {"name": "User", "kind": "OBJECT",
                 "fields": [{"name": "id", "type": {"kind": "SCALAR", "name": "ID", "ofType": None}, "description": ""}],
                 "description": ""},
            ]}}
        }
        apk = make_apk({
            "assets/schema.json": json.dumps(schema),
            "AndroidManifest.xml": "<manifest/>",
        })
        with zipfile.ZipFile(apk) as z:
            result = AssetsGraphQLStrategy(z).extract()
        assert any(t["name"] == "User" for t in result["types"])

    def test_empty_apk(self):
        apk = make_apk({"AndroidManifest.xml": "<manifest/>"})
        with zipfile.ZipFile(apk) as z:
            result = AssetsGraphQLStrategy(z).extract()
        assert result["operations"] == []


# ── ObfuscatedDexStrategy ─────────────────────────────────────────────────────

class TestObfuscatedDexStrategy:
    def _make_dex_apk(self, strings):
        dex = build_dex(strings)
        return make_apk({"classes.dex": dex, "AndroidManifest.xml": "<manifest/>"})

    def test_finds_query(self):
        apk = self._make_dex_apk([
            "query GetProfile($userId: ID!) { user(id: $userId) { id email phoneNumber } }",
            "a", "b", "com.example.SomeClass",
        ])
        with zipfile.ZipFile(apk) as z:
            result = ObfuscatedDexStrategy(z).extract()
        assert any(o["name"] == "GetProfile" for o in result["operations"])

    def test_finds_mutation(self):
        apk = self._make_dex_apk([
            "mutation DeleteAccount($userId: ID!) { deleteAccount(userId: $userId) { success message } }",
        ])
        with zipfile.ZipFile(apk) as z:
            result = ObfuscatedDexStrategy(z).extract()
        assert any(o["type"] == "mutation" for o in result["operations"])

    def test_ignores_short_strings(self):
        apk = self._make_dex_apk(["hi", "ok", "a"])
        with zipfile.ZipFile(apk) as z:
            result = ObfuscatedDexStrategy(z).extract()
        assert result["operations"] == []

    def test_multiple_dex_files(self):
        dex1 = build_dex(["query A($id: ID!) { a(id: $id) { id name email address } }"])
        dex2 = build_dex(["mutation B($x: ID!) { b(x: $x) { ok message result } }"])
        apk = make_apk({
            "classes.dex": dex1,
            "classes2.dex": dex2,
            "AndroidManifest.xml": "<manifest/>",
        })
        with zipfile.ZipFile(apk) as z:
            result = ObfuscatedDexStrategy(z).extract()
        names = [o["name"] for o in result["operations"]]
        assert "A" in names
        assert "B" in names

    def test_type_inference_from_variables(self):
        apk = self._make_dex_apk([
            "mutation CreateReservation($input: CreateReservationInput!) { createReservation(input: $input) { id } }",
        ])
        with zipfile.ZipFile(apk) as z:
            result = ObfuscatedDexStrategy(z).extract()
        type_names = [t["name"] for t in result["types"]]
        assert "CreateReservationInput" in type_names


# ── ReactNativeStrategy ───────────────────────────────────────────────────────

class TestReactNativeStrategy:
    def test_finds_ops_in_bundle(self):
        bundle = """
var x = `query GetUser($id: ID!) { user(id: $id) { id email name } }`;
var y = `mutation Login($email: String!, $pass: String!) { login(email: $email, pass: $pass) { token } }`;
"""
        apk = make_apk({
            "assets/index.android.bundle": bundle,
            "AndroidManifest.xml": "<manifest/>",
        })
        with zipfile.ZipFile(apk) as z:
            result = ReactNativeStrategy(z).extract()
        assert len(result["operations"]) >= 1

    def test_empty_bundle(self):
        apk = make_apk({
            "assets/index.android.bundle": "var x = 1; console.log('hi');",
            "AndroidManifest.xml": "<manifest/>",
        })
        with zipfile.ZipFile(apk) as z:
            result = ReactNativeStrategy(z).extract()
        assert result["operations"] == []


# ── Extractor (integration) ───────────────────────────────────────────────────

class TestExtractor:
    def test_assets_strategy_wins(self):
        apk = make_apk({
            "assets/Op.graphql": "query GetMe { me { id email } }",
            "AndroidManifest.xml": "<manifest/>",
        })
        result = Extractor(apk).run()
        assert any(o["name"] == "GetMe" for o in result["operations"])

    def test_dedup_across_strategies(self):
        """Same operation in both assets AND dex — should appear once."""
        raw = "query GetUser($id: ID!) { user(id: $id) { id email phoneNumber } }"
        dex = build_dex([raw])
        apk = make_apk({
            "assets/GetUser.graphql": raw,
            "classes.dex": dex,
            "AndroidManifest.xml": "<manifest/>",
        })
        result = Extractor(apk).run()
        names = [o["name"] for o in result["operations"]]
        assert names.count("GetUser") == 1

    def test_no_graphql_apk(self):
        apk = make_apk({
            "AndroidManifest.xml": "<manifest/>",
            "classes.dex": b"not a dex file",
        })
        result = Extractor(apk).run()
        assert result["operations"] == []
        assert result["strategy"] == "none"

    def test_result_has_strategy_field(self):
        apk = make_apk({
            "assets/X.graphql": "query X { x { id } }",
            "AndroidManifest.xml": "<manifest/>",
        })
        result = Extractor(apk).run()
        assert "strategy" in result
        assert result["strategy"] != ""


# ── JSON Reporter ─────────────────────────────────────────────────────────────

class TestJsonReporter:
    def test_writes_valid_json(self, tmp_path):
        result = {
            "operations": [{"name": "GetUser", "type": "query", "variables": [], "fields": [], "raw": "query GetUser { me { id } }"}],
            "types": [],
            "strategy": "test",
        }
        out = tmp_path / "schema.json"
        write_json(result, out)
        data = json.loads(out.read_text())
        assert data["meta"]["tool"] == "apka-P"
        assert data["summary"]["queries"] == 1
        assert len(data["operations"]) == 1

    def test_summary_counts(self, tmp_path):
        result = {
            "operations": [
                {"name": "A", "type": "query", "variables": [], "fields": [], "raw": ""},
                {"name": "B", "type": "mutation", "variables": [], "fields": [], "raw": ""},
                {"name": "C", "type": "mutation", "variables": [], "fields": [], "raw": ""},
                {"name": "D", "type": "subscription", "variables": [], "fields": [], "raw": ""},
            ],
            "types": [{"name": "User", "kind": "OBJECT", "fields": []}],
            "strategy": "test",
        }
        out = tmp_path / "schema.json"
        write_json(result, out)
        data = json.loads(out.read_text())
        assert data["summary"]["queries"] == 1
        assert data["summary"]["mutations"] == 2
        assert data["summary"]["subscriptions"] == 1
        assert data["summary"]["types"] == 1
