"""
Extractor — runs ALL strategies, combines results, detects endpoints.
"""

import zipfile
import subprocess
import shutil
import tempfile
from pathlib import Path
from rich.console import Console

from .strategies.assets_graphql import AssetsGraphQLStrategy
from .strategies.apollo_kotlin import ApolloKotlinStrategy
from .strategies.react_native import ReactNativeStrategy
from .strategies.string_grep import StringGrepStrategy
from .strategies.obfuscated_dex import ObfuscatedDexStrategy
from .strategies.endpoint_detector import EndpointDetector

console = Console()


class Extractor:
    def __init__(self, apk_path: Path, apktool_bin: str = "apktool", verbose: bool = False):
        self.apk_path = apk_path
        self.apktool_bin = apktool_bin
        self.verbose = verbose
        self._tmpdir = None

    def log(self, msg: str):
        if self.verbose:
            console.print(f"  [dim]{msg}[/dim]")

    def run(self) -> dict:
        combined_ops   = []
        combined_types = []
        matched_strategies = []

        apk_zip = zipfile.ZipFile(self.apk_path, "r")

        # ── Endpoint detection ───────────────────────────────────────
        try:
            ep_result = EndpointDetector(apk_zip, verbose=self.verbose).extract()
            endpoints = ep_result.get("endpoints", [])
        except Exception:
            endpoints = []

        if endpoints:
            self.log(f"Endpoints found: {endpoints}")

        # ── ZIP-based strategies ─────────────────────────────────────
        for strategy in [
            AssetsGraphQLStrategy(apk_zip, verbose=self.verbose),
            ObfuscatedDexStrategy(apk_zip, verbose=self.verbose),
            ReactNativeStrategy(apk_zip, verbose=self.verbose),
        ]:
            self.log(f"Trying: {strategy.name}")
            try:
                result = strategy.extract()
            except Exception as e:
                self.log(f"{strategy.name} error: {e}")
                result = {}

            if result and self._has_data(result):
                ops   = result.get("operations", [])
                types = result.get("types", [])
                console.print(f"  [green]✓[/green] {strategy.name}: [cyan]{len(ops)}[/cyan] ops")
                combined_ops.extend(ops)
                combined_types.extend(types)
                matched_strategies.append(strategy.name)

        apk_zip.close()

        # ── smali strategies (need apktool) ──────────────────────────
        if shutil.which(self.apktool_bin):
            decompiled = self._decompile()
            if decompiled:
                for strategy in [
                    ApolloKotlinStrategy(decompiled, verbose=self.verbose),
                    StringGrepStrategy(decompiled, verbose=self.verbose),
                ]:
                    self.log(f"Trying: {strategy.name}")
                    try:
                        result = strategy.extract()
                    except Exception as e:
                        self.log(f"{strategy.name} error: {e}")
                        result = {}

                    if result and self._has_data(result):
                        ops   = result.get("operations", [])
                        types = result.get("types", [])
                        console.print(f"  [green]✓[/green] {strategy.name}: [cyan]{len(ops)}[/cyan] ops")
                        combined_ops.extend(ops)
                        combined_types.extend(types)
                        matched_strategies.append(strategy.name)

                self._cleanup()

        # ── Deduplicate by (name, type) ──────────────────────────────
        seen = set()
        unique_ops = []
        for op in combined_ops:
            key = (op.get("name", ""), op.get("type", ""))
            if key not in seen and key[0]:
                seen.add(key)
                unique_ops.append(op)

        seen_t = set()
        unique_types = []
        for t in combined_types:
            n = t.get("name", "")
            if n and n not in seen_t:
                seen_t.add(n)
                unique_types.append(t)

        return {
            "operations": unique_ops,
            "types": unique_types,
            "endpoints": endpoints,
            "strategy": " + ".join(matched_strategies) if matched_strategies else "none",
        }

    def _decompile(self) -> Path | None:
        self._tmpdir = tempfile.mkdtemp(prefix="apkap_")
        out = Path(self._tmpdir) / "decompiled"
        cmd = [self.apktool_bin, "d", str(self.apk_path), "-o", str(out), "-f", "--no-res"]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=180)
            return out
        except Exception as e:
            console.print(f"  [yellow]apktool: {e}[/yellow]")
            return None

    def _cleanup(self):
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _has_data(self, result: dict) -> bool:
        return bool(result.get("operations") or result.get("types"))
