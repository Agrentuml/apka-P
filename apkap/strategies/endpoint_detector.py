"""
Endpoint Detector

Finds GraphQL endpoint URLs from DEX string pool.
GraphQL endpoints are hardcoded strings like:
  https://api.example.com/graphql
  https://onegraph.example.com/
  https://api.example.com/api/graphql/
"""

import re
import struct
import zipfile
from .base import BaseStrategy


# URL patterns that likely point to GraphQL endpoints
GRAPHQL_URL_RE = re.compile(
    r'https?://[a-zA-Z0-9._/-]+(?:graphql|gql|graph|onegraph)[a-zA-Z0-9._/-]*',
    re.IGNORECASE
)

# Also catch /graphql path on any domain
API_URL_RE = re.compile(
    r'https?://[a-zA-Z0-9._-]+(?:\.[a-z]{2,})/[a-zA-Z0-9/_.-]*graphql[a-zA-Z0-9/_.-]*',
    re.IGNORECASE
)


class EndpointDetector(BaseStrategy):
    name = "Endpoint Detector"

    DEX_MAGIC = b"dex\n"

    def extract(self) -> dict:
        if not isinstance(self.source, zipfile.ZipFile):
            return {}

        dex_files = sorted(
            n for n in self.source.namelist()
            if re.match(r"classes\d*\.dex", n)
        )

        endpoints = set()

        for dex_name in dex_files:
            try:
                data = self.source.read(dex_name)
                strings = self._extract_strings(data)
                for s in strings:
                    if self._is_endpoint(s):
                        endpoints.add(s.strip())
            except Exception:
                pass

        return {"endpoints": sorted(endpoints)}

    def _is_endpoint(self, s: str) -> bool:
        if len(s) < 10 or len(s) > 200:
            return False
        return bool(GRAPHQL_URL_RE.search(s) or API_URL_RE.search(s))

    def _extract_strings(self, data: bytes) -> list[str]:
        if data[:4] != self.DEX_MAGIC or len(data) < 112:
            return []
        try:
            size = struct.unpack_from("<I", data, 56)[0]
            off  = struct.unpack_from("<I", data, 60)[0]
        except struct.error:
            return []
        if size > 5_000_000 or off > len(data):
            return []

        strings = []
        for i in range(size):
            id_off = off + i * 4
            if id_off + 4 > len(data):
                break
            str_off = struct.unpack_from("<I", data, id_off)[0]
            if str_off >= len(data):
                continue
            try:
                length, start = self._uleb128(data, str_off)
                if length < 8 or length > 300:
                    continue
                s = data[start:start+length].decode("utf-8", errors="ignore")
                if s.startswith("http"):
                    strings.append(s)
            except Exception:
                continue
        return strings

    def _uleb128(self, data: bytes, offset: int) -> tuple[int, int]:
        result, shift = 0, 0
        while offset < len(data):
            b = data[offset]; offset += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
        return result, offset
