<div align="center">

```
 █████╗ ██████╗ ██╗  ██╗ █████╗       ██████╗ 
██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗      ██╔══██╗
███████║██████╔╝█████╔╝ ███████║█████╗██████╔╝
██╔══██║██╔═══╝ ██╔═██╗ ██╔══██║╚════╝██╔═══╝ 
██║  ██║██║     ██║  ██╗██║  ██║      ██║     
╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝      ╚═╝     
```

# apka-P &nbsp;·&nbsp; APK API

**Extract GraphQL schema from Android APKs — when introspection is disabled.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Author](https://img.shields.io/badge/author-Agrentuml-purple?style=flat-square)](https://bugcrowd.com/Agrentuml)

</div>

---

## What is this?

When you're doing bug bounty on an app with GraphQL — the first thing you try is introspection. And the first thing they do is disable it.

**apka-P** solves this by extracting the full GraphQL schema directly from the Android APK file — no introspection request needed, no server interaction at all.

It reads what the app already knows: every query, mutation, and subscription the app can make, including argument names, types, and the GraphQL endpoint URL.

---

## Demo

```
Queries:       142
Mutations:     89
Subscriptions: 3
Endpoint:      https://api.example.com/graphql
```

Opens as a local interactive HTML explorer — searchable by operation name, arguments, and response fields.

---

## How it works

apka-P runs multiple extraction strategies in order, combining all results:

| Strategy | What it does | Requires |
|----------|-------------|----------|
| **Assets (.graphql)** | Finds raw `.graphql` files shipped inside the APK | nothing |
| **Assets (schema.json)** | Finds bundled introspection JSON | nothing |
| **DEX string pool** | Reads GraphQL strings directly from binary DEX — works even with ProGuard obfuscation | nothing |
| **React Native** | Extracts operations from JS bundle (`index.android.bundle`) | nothing |
| **Apollo Kotlin (smali)** | Parses decompiled smali for `OPERATION_DOCUMENT` strings | apktool |
| **String grep** | Fallback — scans all smali for GraphQL patterns | apktool |

> ProGuard renames class names (`GetUserQuery` → `a`) but **never touches string values**. The GraphQL operation strings sit untouched in the DEX string pool. That's the core insight.

---

## Install

```bash
git clone https://github.com/Agrentuml/apka-P
cd apka-P
pip install -e .
```

Optional but recommended — install `apktool` for smali-based strategies:

```bash
# macOS
brew install apktool

# Linux
sudo apt install apktool
```

---

## Usage

```bash
# Basic
apka-p target.apk

# Verbose — see which strategies fire and why
apka-p target.apk -v

# Custom output directory
apka-p target.apk -o ~/bug-bounty/results/

# Skip HTML (JSON only)
apka-p target.apk --no-html

# Version
apka-p --version
```

Output goes to `./apkap_output/<apk_name>/`:
```
apkap_output/target/
├── schema.html   ← open this in browser
└── schema.json   ← raw data, import into Burp/InQL
```

---

## Output

The HTML report is a self-contained interactive explorer:

- **Sidebar** — all operations listed with type indicators, filterable by Queries / Mutations / Subscriptions
- **Smart search** — search by operation name, argument names, response fields, or raw query text
- **Detail panel** — arguments table with Required flags, response field tags, full raw query with copy button
- **Endpoint** — auto-detected GraphQL URL shown at the top

---

## Results across different APK types

| APK type | Operations found | Strategy used |
|----------|-----------------|---------------|
| Apollo Kotlin + assets | 200+ | Assets + DEX + smali |
| Apollo Kotlin obfuscated | 100+ | DEX string pool |
| Small GraphQL surface | ~8 | DEX string pool |
| React Native + Apollo | varies | JS bundle |

---

## Bug bounty tips

1. Look for mutations with user ID parameters → **IDOR candidates**
2. Look for admin/internal-sounding operation names → **privilege escalation**
3. Cross-reference found mutations with Burp traffic to confirm they're active
4. Use the **Fields** search scope to find operations returning sensitive data (`email`, `phone`, `address`)
5. Mutations with `delete`, `update`, `admin`, `internal` in the name → **test first**

---

## Contributing

This tool was built for the bug bounty community. If you want to add:
- A new extraction strategy (different GraphQL client, new APK format)
- Better type inference from DEX
- REST API endpoint extraction
- iOS IPA support

Open a PR or issue. The strategy system is modular — adding a new strategy is straightforward (see `apkap/strategies/base.py`).

---

## Roadmap

- [ ] REST API endpoint extraction from APKs
- [ ] iOS IPA support
- [ ] Interactive mode: choose what to extract (GraphQL / REST / both)
- [ ] GitHub Actions CI
- [ ] PyPI release (`pip install apka-p`)

---

## Author

**Agrentuml** — bug bounty hunter

[![Bugcrowd](https://img.shields.io/badge/Bugcrowd-Agrentuml-orange?style=flat-square&logo=bugcrowd)](https://bugcrowd.com/Agrentuml)
[![GitHub](https://img.shields.io/badge/GitHub-Agrentuml-black?style=flat-square&logo=github)](https://github.com/Agrentuml)

---

*apka-P — because introspection being disabled is not your problem.*
