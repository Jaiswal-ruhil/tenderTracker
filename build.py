import sys
import os
import subprocess
import unittest

def run_tests():
    print("=========================================")
    print("RUNNING UNIT TESTS...")
    print("=========================================")
    # Add src and its subdirectories to sys.path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'core'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'gui'))
    
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir='tests')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        print("\n[FAIL] UNIT TESTS FAILED. Aborting build.")
        sys.exit(1)
    print("\n[SUCCESS] All unit tests passed successfully!")

def check_imports():
    print("\n=========================================")
    print("CHECKING DEPENDENCIES...")
    print("=========================================")
    required_mods = ["openpyxl", "selenium", "webdriver_manager", "pypdf", "sqlite3", "faiss", "numpy"]
    missing = []
    for mod in required_mods:
        try:
            __import__(mod)
            print(f"  - {mod}: OK")
        except ImportError:
            print(f"  - {mod}: MISSING")
            missing.append(mod)
            
    if missing:
        print(f"\n[FAIL] Missing required dependencies: {', '.join(missing)}")
        print("Please install them before compiling (e.g., pip install openpyxl selenium webdriver-manager pypdf).")
        sys.exit(1)
    print("\n[SUCCESS] All dependencies are available!")

def compile_app():
    print("\n=========================================")
    print("COMPILING WITH PYINSTALLER...")
    print("=========================================")
    spec_file = "TenderTracker.spec"
    if not os.path.exists(spec_file):
        print(f"[FAIL] Spec file {spec_file} not found.")
        sys.exit(1)
        
    try:
        import PyInstaller
    except ImportError:
        print("[FAIL] PyInstaller is not installed. Run 'pip install pyinstaller' to compile.")
        sys.exit(1)
        
    print(f"Running PyInstaller on {spec_file}...")
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", spec_file], check=True)
        print("\n[SUCCESS] Standalone executable built successfully in the dist/ folder!")
    except subprocess.CalledProcessError as e:
        print(f"\n[FAIL] PyInstaller compilation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # If a local virtual environment exists and we're not running from it, re-execute with it
    venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        norm_venv = os.path.normpath(os.path.abspath(venv_python))
        norm_sys = os.path.normpath(os.path.abspath(sys.executable))
        if norm_sys != norm_venv:
            print(f"Relaunching build script inside virtual environment: {venv_python}")
            result = subprocess.run([venv_python] + sys.argv)
            sys.exit(result.returncode)

    check_imports()
    run_tests()
    compile_app()
