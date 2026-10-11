#!/usr/bin/env python3
"""Improve the macOS cwd anchor for the Intel test build.

The macOS patch adds a simple anchor to both Program.cs files:
    if (OperatingSystem.IsMacOS() && Directory.GetCurrentDirectory() == "/")
    {
        Directory.SetCurrentDirectory(AppContext.BaseDirectory);
    }
This script replaces that 4-line block with a safer file-existence check:
only re-anchor to the app directory when config.conf is NOT in the current
working directory but IS in the app directory. That way a terminal launch
from a folder that has its own config keeps working.

Idempotent: files that already carry the improved block are skipped.
Run from the cloned SubScraper source root (the workflow does `cd src` first).

Exit 0 when every target was upgraded (or already upgraded), 1 otherwise so
the workflow fails loudly instead of shipping a build without the fix.
"""

import sys

TARGETS = ["SubScraper.Cli/Program.cs", "SubScraper.Gui/Program.cs"]
MARKER_A = "OperatingSystem.IsMacOS()"
MARKER_B = 'GetCurrentDirectory() == "/"'
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


def upgrade(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    if any(ALREADY_DONE in line for line in lines):
        print(f"SKIP: {path} already has the improved cwd fix")
        return 0
    out = []
    i = 0
    replaced = 0
    while i < len(lines):
        if MARKER_A in lines[i] and MARKER_B in lines[i]:
            indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
            out.append(NEW_BLOCK.format(indent=indent))
            i += 4  # skip the simple 4-line block: if / { / SetCurrentDirectory / }
            replaced += 1
        else:
            out.append(lines[i])
            i += 1
    if not replaced:
        print(f"WARN: pattern not found in {path} (patch may have changed)")
        return 1
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)
    print(f"OK: {path} upgraded ({replaced} block)")
    return 0


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
