"""
Assets GraphQL Strategy

Some apps ship raw .graphql files or schema.json in assets.
This is the jackpot — zero parsing needed.

Also checks for Apollo's persisted query manifests.
"""

import json
import zipfile
from pathlib import PurePosixPath
from .base import BaseStrategy, parse_graphql_string


class AssetsGraphQLStrategy(BaseStrategy):
    name = "Assets (.graphql / schema.json)"

    # Files that contain introspection result directly
    INTROSPECTION_FILENAMES = {
        "schema.json",
        "introspection.json",
        "graphql.json",
        "schema.graphql.json",
        "api.json",
    }

    def extract(self) -> dict:
        if not isinstance(self.source, zipfile.ZipFile):
            return {}

        operations = []
        types = []
        found_files = []

        for name in self.source.namelist():
            p = PurePosixPath(name)

            # Raw .graphql files
            if p.suffix == ".graphql":
                try:
                    content = self.source.read(name).decode("utf-8", errors="ignore")
                    self.log(f"Parsing {name}")
                    parsed = parse_graphql_string(content)
                    operations.extend(parsed)
                    found_files.append(name)
                except Exception as e:
                    self.log(f"Failed to parse {name}: {e}")

            # JSON schema files
            elif p.name.lower() in self.INTROSPECTION_FILENAMES:
                try:
                    content = json.loads(self.source.read(name))
                    self.log(f"Found schema JSON: {name}")
                    extracted_types = self._parse_introspection_json(content)
                    types.extend(extracted_types)
                    found_files.append(name)
                except Exception as e:
                    self.log(f"Failed to parse {name}: {e}")

            # Apollo persisted query manifest
            elif p.name in ("persistedQueriesManifest.json", "queries.json", "operations.json"):
                try:
                    content = json.loads(self.source.read(name))
                    self.log(f"Found persisted queries: {name}")
                    ops = self._parse_persisted_queries(content)
                    operations.extend(ops)
                    found_files.append(name)
                except Exception as e:
                    self.log(f"Failed to parse {name}: {e}")

        if found_files:
            self.log(f"Assets found: {found_files}")

        return {"operations": operations, "types": types}

    def _parse_introspection_json(self, data: dict) -> list[dict]:
        """Parse GraphQL introspection result JSON into type list."""
        types = []
        try:
            schema = data.get("data", data).get("__schema", {})
            for t in schema.get("types", []):
                if t["name"].startswith("__"):
                    continue
                kind = t.get("kind", "OBJECT")
                fields_key = "fields" if kind in ("OBJECT", "INTERFACE") else "inputFields"
                raw_fields = t.get(fields_key) or []
                fields = []
                for f in raw_fields:
                    fields.append({
                        "name": f["name"],
                        "type": self._type_str(f.get("type", {})),
                        "description": f.get("description", "") or "",
                    })
                types.append({
                    "name": t["name"],
                    "kind": kind,
                    "fields": fields,
                    "description": t.get("description", "") or "",
                    "source": "introspection.json",
                })
        except Exception:
            pass
        return types

    def _type_str(self, type_node: dict) -> str:
        if not type_node:
            return "Unknown"
        kind = type_node.get("kind", "")
        name = type_node.get("name")
        of_type = type_node.get("ofType")
        if kind == "NON_NULL":
            return f"{self._type_str(of_type)}!"
        elif kind == "LIST":
            return f"[{self._type_str(of_type)}]"
        return name or "Unknown"

    def _parse_persisted_queries(self, data) -> list[dict]:
        operations = []
        # Format: {"queryId": "body"} or [{"id": ..., "body": ...}]
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, str) and val.strip().startswith(("query", "mutation", "subscription")):
                    ops = parse_graphql_string(val)
                    operations.extend(ops)
        elif isinstance(data, list):
            for item in data:
                body = item.get("body") or item.get("query") or item.get("document", "")
                if body:
                    ops = parse_graphql_string(body)
                    operations.extend(ops)
        return operations
