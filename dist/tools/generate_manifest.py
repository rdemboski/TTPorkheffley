"""
generate_manifest.py
--------------------
Scans a directory for .mf phase files, TTPHEngine.exe, and settings.json,
then writes a manifest file that the TTPHLauncher PatcherService can parse.

Usage:
    python generate_manifest.py [--dir PATH] [--version VERSION] [--out FILE]
    python generate_manifest.py --file PATH [--version VERSION] [--out FILE]

Defaults:
    --dir      ../../../TTPorkheffley-Resources  (relative to this script)
    --version  1.0.0
    --out      manifest.txt                      (written in --dir by default,
                                                  or specify a full path, e.g.
                                                  TTPHWebAPI/wwwroot/manifest.txt)

Single-file patch mode (--file):
    Updates only the specified file's entry in an existing manifest without
    touching any other entries. Useful when only one file has changed, e.g.:
        python generate_manifest.py --file build\\PrivacyStart.dist\\TTPHEngine.exe
                                    --out TTPHWebAPI\\wwwroot\\manifest.txt

The generated manifest format:
    REQUIRED_INSTALL_FILES=phase_3.mf:3 phase_3.5.mf:3 ... settings.json:3
    FILE_phase_3.mf.current=1.0.0
    FILE_phase_3.mf.1.0.0=<bytesize> <md5hex>
    ...
"""

import argparse
import hashlib
import os
import re
import sys


# Flag appended after each filename in REQUIRED_INSTALL_FILES.
# The launcher strips it (splits on ':'), so the value is arbitrary;
# 3 is the value TTR uses to mean "required".
FILE_FLAG = "3"


def md5_of_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def patch_manifest(manifest_path: str, file_path: str, version: str):
    """Update a single file's entry in an existing manifest."""
    name = os.path.basename(file_path)
    size = os.path.getsize(file_path)
    md5 = md5_of_file(file_path)

    if not os.path.isfile(manifest_path):
        print(f"ERROR: manifest not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Update REQUIRED_INSTALL_FILES — add the file if not already listed.
    req_pattern = re.compile(r"(REQUIRED_INSTALL_FILES=)(.*)")
    match = req_pattern.search(text)
    if match:
        entries = match.group(2).split()
        names_in_list = [e.split(":")[0] for e in entries]
        if name not in names_in_list:
            entries.append(f"{name}:{FILE_FLAG}")
            text = req_pattern.sub(
                match.group(1) + " ".join(entries), text, count=1
            )

    # Update or insert FILE_<name>.current
    current_key = f"FILE_{name}.current"
    current_line = f"{current_key}={version}"
    if re.search(re.escape(current_key), text):
        text = re.sub(rf"{re.escape(current_key)}=\S+", current_line, text)
    else:
        text = text.rstrip("\n") + f"\n{current_line}\n"

    # Update or insert FILE_<name>.<version>
    hash_key = f"FILE_{name}.{version}"
    hash_line = f"{hash_key}={size} {md5}"
    if re.search(re.escape(hash_key), text):
        text = re.sub(rf"{re.escape(hash_key)}=.*", hash_line, text)
    else:
        text = text.rstrip("\n") + f"\n{hash_line}\n"

    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print(f"Patched {manifest_path}")
    print(f"  {name}  ({size:,} bytes)  {md5}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.normpath(
        os.path.join(script_dir, "..", "..", "..", "TTPorkheffley-Resources")
    )

    parser = argparse.ArgumentParser(description="Generate or patch a TTPH launcher manifest.")
    parser.add_argument(
        "--dir",
        default=default_dir,
        help=f"Directory to scan for .mf files (default: {default_dir})",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Path to a single file to update in an existing manifest (patch mode).",
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Version string to embed in the manifest (default: 1.0.0)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for manifest.txt (default: <dir>/manifest.txt)",
    )
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Patch mode — update a single file entry in an existing manifest
    # -----------------------------------------------------------------------
    if args.file:
        file_path = os.path.abspath(args.file)
        if not os.path.isfile(file_path):
            print(f"ERROR: file not found: {file_path}", file=sys.stderr)
            sys.exit(1)

        scan_dir = os.path.abspath(args.dir)
        out_path = args.out or os.path.join(scan_dir, "manifest.txt")
        patch_manifest(out_path, file_path, args.version)
        return

    # -----------------------------------------------------------------------
    # Full scan mode — regenerate entire manifest from directory
    # -----------------------------------------------------------------------
    scan_dir = os.path.abspath(args.dir)
    if not os.path.isdir(scan_dir):
        print(f"ERROR: directory not found: {scan_dir}", file=sys.stderr)
        sys.exit(1)

    # Collect .mf files, sorted for a stable output order.
    mf_files = sorted(
        f for f in os.listdir(scan_dir) if f.lower().endswith(".mf")
    )

    if not mf_files:
        print(f"ERROR: no .mf files found in {scan_dir}. Aborting to avoid overwriting a good manifest.", file=sys.stderr)
        sys.exit(1)

    # Always append TTPHEngine.exe and settings.json if they exist.
    all_files = list(mf_files)
    for extra in ("TTPHEngine.exe", "settings.json"):
        if os.path.isfile(os.path.join(scan_dir, extra)):
            all_files.append(extra)
        else:
            print(f"WARNING: {extra} not found in {scan_dir}, skipping.", file=sys.stderr)

    out_path = args.out or os.path.join(scan_dir, "manifest.txt")
    version = args.version

    lines = []

    # REQUIRED_INSTALL_FILES line
    entries = " ".join(f"{name}:{FILE_FLAG}" for name in all_files)
    lines.append(f"REQUIRED_INSTALL_FILES={entries}")
    lines.append("")

    # Per-file current + hash entries
    for name in all_files:
        full_path = os.path.join(scan_dir, name)
        size = os.path.getsize(full_path)
        md5 = md5_of_file(full_path)

        lines.append(f"FILE_{name}.current={version}")
        lines.append(f"FILE_{name}.{version}={size} {md5}")

    lines.append("")  # trailing newline

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print(f"Manifest written to: {out_path}")
    print(f"  Version : {version}")
    print(f"  Files   : {len(all_files)}")
    for name in all_files:
        full_path = os.path.join(scan_dir, name)
        size = os.path.getsize(full_path)
        print(f"    {name}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
