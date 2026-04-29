import json
from pathlib import Path
from datetime import datetime


def write_json(result: dict, path: Path):
    ops = result.get("operations", [])
    output = {
        "meta": {
            "tool": "apka-P [APK API]",
            "version": "0.2.0",
            "timestamp": datetime.now().isoformat(),
            "strategy": result.get("strategy", "unknown"),
        },
        "endpoints": result.get("endpoints", []),
        "summary": {
            "queries":       len([o for o in ops if o["type"] == "query"]),
            "mutations":     len([o for o in ops if o["type"] == "mutation"]),
            "subscriptions": len([o for o in ops if o["type"] == "subscription"]),
            "types":         len(result.get("types", [])),
        },
        "operations": ops,
        "types": result.get("types", []),
    }
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
