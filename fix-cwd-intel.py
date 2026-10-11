#!/usr/bin/env python3
"""Set macOS cwd to the app directory for the Intel test build.

The macOS patch adds a simple anchor to SubScraper.Gui/Program.cs:
    if (OperatingSystem.IsMacOS() && Directory.GetCurrentDirectory() == "/")
    {
        Directory.SetCurrentDirectory(AppContext.BaseDirectory);
    }
The CLI (SubScraper.Cli/Program.cs) has no such anchor in the patch.
This script replaces/adds an UNCONDITIONAL anchor on macOS:
always set the working directory to the app folder at startup,
matching what the .command launcher does (cd "$(dirname "$0")").
This avoids the fragile "check if config.conf exists" logic which
breaks when stray files exist in $HOME from earlier buggy runs.

Idempotent: files that already carry the unconditional anchor are skipped.
Run from the cloned SubScraper source root (the workflow does `cd src` first).

Exit 0 when every target was upgraded (or already upgraded), 1 otherwise so
the workflow fails loudly instead of shipping a build without the fix.
"""

import re
import sys

TARGETS = ["SubScraper.Cli/Program.cs", "SubScraper.Gui/Program.cs"]
ALREADY_DONE = 'Directory.SetCurrentDirectory(AppContext.BaseDirectory); // macOS: always use app dir'

NEW_BLOCK_GUI = """{indent}// macOS: always anchor cwd to the app directory (like the .command launcher).
{indent}if (OperatingSystem.IsMacOS())
{indent}{{
{indent}    Directory.SetCurrentDirectory(AppContext.BaseDirectory); // macOS: always use app dir
{indent}}}
"""

NEW_BLOCK_CLI = """{indent}// macOS: always anchor cwd to the app directory (like the .command launcher).
{indent}if (OperatingSystem.IsMacOS())
{indent}{{
{indent}    Directory.SetCurrentDirectory(AppContext.BaseDirectory); // macOS: always use app dir
{indent}}}
"""

# Flexible regex for the old 4-line conditional block (GUI)
OLD_PATTERN = re.compile(
    r'[ \t]*//[^\n]*\n(?:[ \t]*//[^\n]*\n)*'
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
        print(f"SKIP: {path} already has the unconditional macOS cwd anchor")
        return 0

    is_cli = "SubScraper.Cli" in path
    new_block_template = NEW_BLOCK_CLI if is_cli else NEW_BLOCK_GUI

    # Try to replace the old conditional block (GUI case)
    def repl(m):
        first_line = m.group(0).split('\n')[0]
        # Find the indent of the 'if' line (skip comment lines)
        for line in m.group(0).split('\n'):
            if 'if' in line and 'IsMacOS' in line:
                indent = line[:len(line) - len(line.lstrip())]
                break
        else:
            indent = "            "
        return new_block_template.format(indent=indent)

    new_content, n = OLD_PATTERN.subn(repl, content)
    if n > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"OK: {path} upgraded ({n} block replaced with unconditional anchor)")
        return 0

    # No old block found: insert at start of Main() (CLI case)
    if is_cli:
        m = CLI_MAIN_PATTERN.search(content)
        if m:
            indent = "        "
            insert = new_block_template.format(indent=indent) + "\n"
            pos = m.end()
            new_content = content[:pos] + insert + content[pos:]
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"OK: {path} upgraded (unconditional anchor inserted at Main)")
            return 0

    print(f"WARN: pattern not found in {path} (patch may have changed)")
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
