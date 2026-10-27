"""Static validation that does not require Blender."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "bm_import_export_menu_manager"
REQUIRED = {
    "__init__.py",
    "blender_manifest.toml",
    "CHANGELOG.md",
    "LICENSE.txt",
    "preferences.py",
    "README.md",
    "runtime.py",
}


def main() -> None:
    files = {path.name for path in SOURCE.iterdir() if path.is_file()}
    missing = REQUIRED - files
    if missing:
        raise SystemExit(f"Missing source files: {sorted(missing)}")

    manifest = tomllib.loads((SOURCE / "blender_manifest.toml").read_text(encoding="utf-8"))
    if manifest["id"] != "bm_import_export_menu_manager":
        raise SystemExit("Unexpected extension ID")
    if tuple(int(part) for part in manifest["version"].split(".")) < (1, 0, 0):
        raise SystemExit("Invalid extension version")
    if tuple(int(part) for part in manifest["blender_version_min"].split(".")) < (5, 2, 0):
        raise SystemExit("Unexpected minimum Blender version")

    for path in SOURCE.glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    leaked = [
        path
        for path in SOURCE.rglob("*")
        if "__pycache__" in path.parts or path.suffix == ".pyc"
    ]
    if leaked:
        raise SystemExit(f"Generated files found in source: {leaked}")

    print(f"Validated BM Import & Export Menu Manager {manifest['version']}")


if __name__ == "__main__":
    main()
