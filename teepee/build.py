"""Build Teepee with PyInstaller.

Usage:
    uv run python build.py

Produces dist/Teepee.zip containing the one-folder bundle.
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "Teepee"


def find_upx():
    """Try to find UPX on PATH or common locations."""
    for candidate in ["upx", r"C:\upx\upx.exe", r"C:\tools\upx\upx.exe"]:
        if shutil.which(candidate):
            return str(Path(shutil.which(candidate)).parent)
    return None


def build_datas():
    """Return --add-data arguments for PyInstaller."""
    args = []
    # sounds directory
    sounds_dir = ROOT / "sounds"
    if sounds_dir.exists():
        args += ["--add-data", f"{sounds_dir}{os.pathsep}sounds"]

    return args


def build_hidden_imports():
    """Return --hidden-import arguments for modules PyInstaller can miss."""
    return [
        "--hidden-import", "telethon",
        "--hidden-import", "cryptg",
        "--hidden-import", "pydub",
        "--hidden-import", "prism",
        "--hidden-import", "prism.core",
        "--hidden-import", "prism.lib",
        "--hidden-import", "json",
        "--hidden-import", "wave",
        "--hidden-import", "struct",
        "--hidden-import", "hashlib",
        "--hidden-import", "sqlite3",
    ]


def make_zip(folder, zip_path):
    """Create a zip archive of the given folder."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, _, files in os.walk(folder):
            for f in files:
                full = Path(root) / f
                arcname = Path(APP_NAME) / full.relative_to(folder)
                zf.write(full, arcname)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Created {zip_path} ({size_mb:.1f} MB)")


def main():
    # Clean previous builds
    for d in [BUILD, DIST]:
        if d.exists():
            shutil.rmtree(d)

    # Ensure Prism is available in the build environment.
    try:
        __import__("prism")
    except Exception as e:
        print(
            "Prism is not installed in this environment. "
            "Install prismatoid in .venv before building.",
            file=sys.stderr,
        )
        print(f"Import error: {e}", file=sys.stderr)
        sys.exit(1)

    cmd1 = [
        sys.executable,
        "versionfile.py",
    ]
    cmd2 = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--noupx" if not find_upx() else f"--upx-dir={find_upx()}",
        "--version-file=vdata.txt",
        # Speed optimisations
        "--optimize", "2",
        "--noconfirm",
        "--clean",
        # Entry point
        str(ROOT / "run.py"),
    ]
    subprocess.run(cmd1, cwd=str(ROOT), check=True)
    cmd2 += build_datas()
    cmd2 += build_hidden_imports()

    # Collect Prism package modules and native assets.
    cmd2 += ["--collect-all", "prism"]

    # Exclude unnecessary large modules
    for mod in ["tkinter", "_tkinter", "unittest", "test", "setuptools",
                "pip", "wheel"]:
        cmd2 += ["--exclude-module", mod]

    print("Running PyInstaller...")
    print(" ".join(cmd2))
    result = subprocess.run(cmd2, cwd=str(ROOT))
    if result.returncode != 0:
        print("PyInstaller failed!", file=sys.stderr)
        sys.exit(1)

    output_dir = DIST / APP_NAME
    if not output_dir.exists():
        print(f"Expected output dir {output_dir} not found!", file=sys.stderr)
        sys.exit(1)

    # Copy sounds if not already included
    dest_sounds = output_dir / "sounds"
    src_sounds = ROOT / "sounds"
    if src_sounds.exists() and not dest_sounds.exists():
        shutil.copytree(src_sounds, dest_sounds)
        print(f"Copied sounds/ to {dest_sounds}")

    # Create zip
    zip_path = DIST / f"{APP_NAME}.zip"
    print("Creating zip archive...")
    make_zip(output_dir, zip_path)

    print("Build complete!")
    print(f"  Folder: {output_dir}")
    print(f"  Archive: {zip_path}")


if __name__ == "__main__":
    main()
