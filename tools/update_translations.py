#!/usr/bin/env python3
"""Extract Qt source texts; optionally compile existing catalogs without network."""
import argparse
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CATALOGS = ROOT / "desktop" / "translations"
SOURCES = [ROOT / "desktop" / "Main.qml", ROOT / "desktop" / "main.py",
           *sorted((ROOT / "desktop" / "felismusic_gui").glob("*.py"))]


def qt_tool(name):
    for candidate in ("pyside6-" + name, name + "6", name):
        executable = shutil.which(candidate)
        if executable:
            return executable
    raise SystemExit(f"Missing Qt Linguist tool: {name}. Install Qt Linguist development tools.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Also compile .qm catalogs")
    parser.add_argument("--output-dir", type=Path, default=CATALOGS,
                        help="Directory for compiled .qm files")
    args = parser.parse_args()
    catalogs = sorted(CATALOGS.glob("felismusic_*.ts")) or [CATALOGS / "felismusic_cs.ts"]
    subprocess.run([qt_tool("lupdate"), *map(str, SOURCES), "-source-language", "cs_CZ",
                    "-locations", "relative", "-ts", *map(str, catalogs)], check=True, cwd=ROOT)
    if args.release:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        executable = qt_tool("lrelease")
        for catalog in catalogs:
            subprocess.run([executable, "-nounfinished", str(catalog), "-qm",
                            str(args.output_dir / (catalog.stem + ".qm"))], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
