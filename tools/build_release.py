"""Build a deterministic Blender extension ZIP from the source directory."""

from __future__ import annotations

from pathlib import Path
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "bm_import_export_menu_manager"
DIST = ROOT / "dist"
INCLUDED_SUFFIXES = {".py", ".toml", ".md", ".txt"}


def main() -> None:
    manifest = tomllib.loads((SOURCE / "blender_manifest.toml").read_text(encoding="utf-8"))
    version = manifest["version"]
    output = DIST / f"BM_Import_Export_Menu_Manager_v{version}.zip"
    paths = sorted(
        SOURCE.rglob("*"),
        key=lambda path: path.relative_to(SOURCE).as_posix(),
    )
    files = [
        path
        for path in paths
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in INCLUDED_SUFFIXES
    ]

    DIST.mkdir(exist_ok=True)
    # Store files without platform-dependent compression so Windows, Linux,
    # and macOS produce the exact same release bytes and checksum.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            relative = path.relative_to(SOURCE).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 10, 26, 12, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())

    print(f"Built {output}")


if __name__ == "__main__":
    main()
