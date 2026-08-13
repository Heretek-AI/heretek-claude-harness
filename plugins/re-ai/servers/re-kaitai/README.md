# re-kaitai

MCP server exposing [Kaitai Struct](https://kaitai.io/) for custom binary format reverse engineering.

## Tools

| Tool | What it does |
|---|---|
| `check_compiler` | Confirm kaitai-struct-compiler is installed |
| `list_known_formats` | List bundled .ksy formats |
| `download_format` | Download a .ksy from the kaitai-formats gallery |
| `compile_format` | Compile .ksy → Python at runtime |
| `parse_with_format` | Parse a binary with a compiled or precompiled format |
| `visualize` | Same as parse_with_format, named for the intent |
| `diff_parses` | Parse two files and return a structural diff |

## Install

```bash
# System dependency
brew install kaitai-struct-compiler   # macOS
scoop install kaitai-struct-compiler  # Windows
# Linux: download prebuilt from https://github.com/kaitai-io/kaitai_struct_compiler/releases

# Python
pip install kaitaistruct
pip install -e ./servers/re-kaitai
```

## Usage pattern (in Claude Code)

```
1. "Decode this firmware blob"
2. Claude identifies the file magic (e.g. LZMA header)
3. Claude downloads the matching .ksy: download_format("lzma")
4. Claude compiles: compile_format("/path/lzma.ksy")
5. Claude parses: parse_with_format(path="/path/blob", ksy_path="/path/lzma.ksy")
6. Claude inspects the parse tree, iterates on the .ksy, re-parses
```

The Kaitai workflow is iterative: compile → parse → fix the schema → re-compile → parse again.
