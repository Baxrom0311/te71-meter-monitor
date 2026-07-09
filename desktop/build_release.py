#!/usr/bin/env python3
"""Cross-platform release build and packaging script.

1. Cleans old build/dist files.
2. Compiles application via PyInstaller and MeterTool.spec.
3. On Windows: Compiles installer via Inno Setup (ISCC).
4. On macOS: Ad-hoc signs the bundle and compresses to .zip.
"""
import os
import sys
import shutil
import subprocess
import zipfile


def clean_folders(root: str):
    """Clean old build and dist outputs."""
    for f in ("build", "dist"):
        p = os.path.join(root, f)
        if os.path.exists(p):
            print(f"[*] Removing old {f} folder...")
            try:
                shutil.rmtree(p)
            except Exception as e:
                print(f"[!] Warning: Failed to remove {p}: {e}")


def run_pyinstaller(root: str):
    """Run PyInstaller with the spec file."""
    spec_path = os.path.join(root, "MeterTool.spec")
    print(f"[*] Compiling app with PyInstaller: {spec_path}")

    # Use virtual environment python if running inside venv
    pyinstaller_bin = "pyinstaller"
    venv_bin = os.path.join(root, ".venv", "bin", "pyinstaller")
    if sys.platform == "win32":
        venv_bin = os.path.join(root, ".venv", "Scripts", "pyinstaller.exe")

    if os.path.exists(venv_bin):
        pyinstaller_bin = venv_bin

    cmd = [pyinstaller_bin, "--clean", spec_path]
    print(f"▶ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=root, check=True)


def package_macos(root: str):
    """Post-build steps for macOS: ad-hoc sign and zip."""
    dist_dir = os.path.join(root, "dist")
    app_path = os.path.join(dist_dir, "MeterTool.app")

    if not os.path.exists(app_path):
        print(f"[!] Error: MeterTool.app not found in {dist_dir}")
        sys.exit(1)

    # 1. Ad-hoc codesign to prevent Gatekeeper crashes on modern macOS
    print("[*] Running ad-hoc codesigning...")
    try:
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", app_path],
            check=True
        )
        print("[*] Ad-hoc codesigning completed.")
    except Exception as e:
        print(f"[!] Warning: codesigning failed: {e}. App will still run but might need quarantine clearing.")

    # 2. Compress into ZIP for easy distribution
    zip_name = os.path.join(dist_dir, "MeterTool_mac.zip")
    print(f"[*] Creating compressed package: {zip_name}")

    # Zip recursively (maintaining execute permissions)
    # Using zip CLI because zipfile module in Python doesn't always preserve executable flags natively
    try:
        subprocess.run(
            ["zip", "-r", "MeterTool_mac.zip", "MeterTool.app"],
            cwd=dist_dir,
            check=True
        )
        print(f"[+] macOS ZIP package created successfully: {zip_name}")
    except Exception:
        # Fallback to python zipfile if zip command is missing
        print("[!] Warning: zip CLI missing, falling back to python zipfile (permissions might not be preserved)...")
        with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, _, files in os.walk(app_path):
                for f in files:
                    fp = os.path.join(root_dir, f)
                    rel = os.path.relpath(fp, dist_dir)
                    zf.write(fp, rel)
        print(f"[+] macOS fallback ZIP created: {zip_name}")


def package_windows(root: str):
    """Post-build steps for Windows: Run Inno Setup Compiler."""
    print("[*] Building Windows Setup Wizard...")
    iss_path = os.path.join(root, "installer.iss")

    # Look for Inno Setup compiler (ISCC)
    iscc_candidates = [
        "iscc",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    iscc_path = None
    for c in iscc_candidates:
        # Try running it or check existence
        try:
            res = subprocess.run([c, "/?"], capture_output=True)
            if res.returncode == 0 or b"Compiler" in res.stderr:
                iscc_path = c
                break
        except FileNotFoundError:
            continue

    if not iscc_path:
        print("[!] Error: Inno Setup (ISCC.exe) not found. Please install Inno Setup 6 and add it to PATH.")
        print("[!] App is compiled but Setup Wizard creation was skipped.")
        return

    cmd = [iscc_path, iss_path]
    print(f"▶ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=root, check=True)
    setup_file = os.path.join(root, "dist", "MeterToolSetup.exe")
    print(f"[+] Windows Setup Wizard created successfully: {setup_file}")


def main():
    root = os.path.dirname(os.path.abspath(__file__))

    print("====================================================")
    print("      Meter Tool Release Build & Package Script     ")
    print("====================================================")

    clean_folders(root)
    run_pyinstaller(root)

    if sys.platform == "darwin":
        package_macos(root)
    elif sys.platform == "win32":
        package_windows(root)
    else:
        print(f"[+] Build completed. Distribution folder: {os.path.join(root, 'dist')}")


if __name__ == "__main__":
    main()
