"""
Base strategy class + shared GraphQL parsing utilities.
"""

from pathlib import Path
import re


class BaseStrategy:
    name = "base"

    def __init__(self, source, verbose: bool = False):
        self.source = source  # Path (smali dir) or ZipFile
        self.verbose = verbose

    def log(self, msg: str):
        if self.verbose:
            from rich.console import Console
            Console().print(f"    [dim][{self.name}] {msg}[/dim]")

    def extract(self) -> dict:
        raise NotImplementedError


def parse_graphql_string(text: str) -> list[dict]:
    """
    Parse a raw GraphQL operation string into structured dicts.
    Uses graphql-core if available, otherwise falls back to regex.
    """
    text = text.strip()
    if not text:
        return []

    try:
        from graphql import parse as gql_parse, OperationDefinitionNode, FragmentDefinitionNode
        doc = gql_parse(text)
        operations = []
        for definition in doc.definitions:
            if isinstance(definition, OperationDefinitionNode):
                op_name = definition.name.value if definition.name else "Anonymous"
                op_type = definition.operation.value  # query/mutation/subscription
                variables = []
                for var_def in definition.variable_definitions:
                    var_name = var_def.variable.name.value
                    var_type = _type_to_str(var_def.type)
                    variables.append({"name": var_name, "type": var_type})
                
                fields = _extract_selection_set(definition.selection_set)
                
                operations.append({
                    "name": op_name,
                    "type": op_type,
                    "variables": variables,
                    "fields": fields,
                    "raw": text,
                })
            elif isinstance(definition, FragmentDefinitionNode):
                pass  # fragments handled separately
        return operations
    except ImportError:
        # Fallback: basic regex parsing
        return _regex_parse(text)
    except Exception:
        # GraphQL parse error — still try to extract what we can
        return _regex_parse(text)


def _type_to_str(type_node) -> str:
    """Convert graphql-core type node to string representation."""
    try:
        from graphql import NonNullTypeNode, ListTypeNode, NamedTypeNode
        if isinstance(type_node, NonNullTypeNode):
            return f"{_type_to_str(type_node.type)}!"
        elif isinstance(type_node, ListTypeNode):
            return f"[{_type_to_str(type_node.type)}]"
        elif isinstance(type_node, NamedTypeNode):
            return type_node.name.value
    except Exception:
        pass
    return "Unknown"


def _extract_selection_set(selection_set, depth: int = 0) -> list[dict]:
    """Recursively extract fields from a selection set."""
    if not selection_set or depth > 5:
        return []
    fields = []
    try:
        from graphql import FieldNode, InlineFragmentNode, FragmentSpreadNode
        for sel in selection_set.selections:
            if isinstance(sel, FieldNode):
                field = {
                    "name": sel.name.value,
                    "alias": sel.alias.value if sel.alias else None,
                }
                if sel.selection_set:
                    field["fields"] = _extract_selection_set(sel.selection_set, depth + 1)
                fields.append(field)
            elif isinstance(sel, InlineFragmentNode) and sel.selection_set:
                fields.extend(_extract_selection_set(sel.selection_set, depth + 1))
    except Exception:
        pass
    return fields


def _regex_parse(text: str) -> list[dict]:
    """
    Fallback regex-based parser when graphql-core isn't available.
    Extracts operation name, type, and variables.
    """
    operations = []
    
    # Match: query/mutation/subscription OperationName($var: Type, ...) {
    op_re = re.compile(
        r'(query|mutation|subscription)\s+(\w+)\s*(\([^)]*\))?\s*\{',
        re.IGNORECASE
    )
    
    for m in op_re.finditer(text):
        op_type = m.group(1).lower()
        op_name = m.group(2)
        vars_str = m.group(3) or ""
        
        variables = []
        if vars_str:
            var_re = re.compile(r'\$(\w+)\s*:\s*([^\s,)]+)')
            for vm in var_re.finditer(vars_str):
                variables.append({
                    "name": vm.group(1),
                    "type": vm.group(2),
                })
        
        operations.append({
            "name": op_name,
            "type": op_type,
            "variables": variables,
            "fields": [],  # Can't reliably extract without full parser
            "raw": text,
        })
    
    return operations
