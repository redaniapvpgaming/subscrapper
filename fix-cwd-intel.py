#!/usr/bin/env python3
"""Improve the macOS cwd anchor for the Intel test build.

The macOS patch adds a simple anchor to SubScraper.Gui/Program.cs:
    if (OperatingSystem.IsMacOS() && Directory.GetCurrentDirectory() == "/")
    {
        Directory.SetCurrentDirectory(AppContext.BaseDirectory);
    }
The CLI (SubScraper.Cli/Program.cs) has no such anchor in the patch.
This script:
- GUI: replaces the 4-line block with a safer file-existence check.
- CLI: inserts the file-existence check at the start of Main().
Only re-anchor to the app directory when config.conf is NOT in the current
working directory but IS in the app directory. That way a terminal launch
from a folder that has its own config keeps working.

Idempotent: files that already carry the improved block are skipped.
Run from the cloned SubScraper source root (the workflow does `cd src` first).

Exit 0 when every target was upgraded (or already upgraded), 1 otherwise so
the workflow fails loudly instead of shipping a build without the fix.
"""

import re
import sys

TARGETS = ["SubScraper.Cli/Program.cs", "SubScraper.Gui/Program.cs"]
ALREADY_DONE = 'File.Exists(Path.Combine(appDir, "config.conf"))'

NEW_BLOCK = """{indent}if (OperatingSystem.IsMacOS())
{indent}{{
{indent}    string appDir = AppContext.BaseDirectory;
{indent}    string cwd = Directory.GetCurrentDirectory();
{indent}    if (!File.Exists(Path.Combine(cwd, "config.conf")) &&
{indent}        File.Exists(Path.Combine(appDir, "config.conf")))
{indent}    {{
{indent}        Directory.SetCurrentDirectory(appDir);
{indent}    }}
{indent}}}
"""

# Flexible regex for the old 4-line block (tolerates whitespace variations)
OLD_PATTERN = re.compile(
    r'[ \t]*if\s*\(\s*OperatingSystem\.IsMacOS\(\)\s*&&\s*'
    r'Directory\.GetCurrentDirectory\(\)\s*==\s*"/"\s*\)\s*\n'
    r'[ \t]*\{\s*\n'
    r'[ \t]*Directory\.SetCurrentDirectory\(AppContext\.BaseDirectory\);\s*\n'
    r'[ \t]*\}\s*\n?',
    re.MULTILINE
)

# For CLI: find "public static async Task Main(string[] args)" followed by "{"
CLI_MAIN_PATTERN = re.compile(
    r'(public static async Task Main\(string\[\] args\)\s*\n[ \t]*\{\s*\n)',
    re.MULTILINE
)


def upgrade(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if ALREADY_DONE in content:
        print(f"SKIP: {path} already has the improved cwd fix")
        return 0

    # Try to replace the old block (GUI case)
    def repl(m):
        first_line = m.group(0).split('\n')[0]
        indent = first_line[:len(first_line) - len(first_line.lstrip())]
        return NEW_BLOCK.format(indent=indent)

    new_content, n = OLD_PATTERN.subn(repl, content)
    if n > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"OK: {path} upgraded ({n} block replaced)")
        return 0

    # No old block found: insert at start of Main() (CLI case)
    m = CLI_MAIN_PATTERN.search(content)
    if m:
        # Insert after the Main() opening brace, with 8-space indent
        indent = "        "
        insert = NEW_BLOCK.format(indent=indent) + "\n"
        pos = m.end()
        new_content = content[:pos] + insert + content[pos:]
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"OK: {path} upgraded (block inserted at Main)")
        return 0

    print(f"WARN: pattern not found in {path} (patch may have changed)")
    for i, line in enumerate(content.split('\n'), 1):
        if 'GetCurrentDirectory' in line or 'SetCurrentDirectory' in line:
            print(f"  DEBUG line {i}: {line.strip()}")
    return 1


def main():
    failed = 0
    for target in TARGETS:
        try:
            failed |= upgrade(target)
        except FileNotFoundError:
            print(f"FAIL: {target} not found (run from the cloned source root)")
            failed = 1
    sys.exit(failed)


if __name__ == "__main__":
    main()
