import os
import sys
import time
import subprocess

def get_mtimes(path):
    mtimes = {}
    for root, dirs, files in os.walk(path):
        # Exclude pycache and virtual environment
        if "__pycache__" in root or ".venv" in root:
            continue
        for f in files:
            if f.endswith('.py'):
                p = os.path.join(root, f)
                try:
                    mtimes[p] = os.path.getmtime(p)
                except Exception:
                    pass
    return mtimes

def main():
    # Detect the correct virtual environment python executable
    venv_py = os.path.join(".venv", "Scripts", "python.exe")
    if os.path.exists(venv_py):
        py_exe = venv_py
    else:
        py_exe = sys.executable

    cmd = [py_exe, "main.py"]
    src_dir = "src"
    
    print(f"[{time.strftime('%H:%M:%S')}] Launching TenderTracker in Hot-Reload Mode...")
    proc = subprocess.Popen(cmd)
    
    last_mtimes = get_mtimes(src_dir)
    last_mtimes[os.path.abspath("main.py")] = os.path.getmtime("main.py")
    
    try:
        while True:
            time.sleep(1)
            
            # Check for changes in python files
            current_mtimes = get_mtimes(src_dir)
            current_mtimes[os.path.abspath("main.py")] = os.path.getmtime("main.py")
            
            changed_file = None
            # Detect modified or new files
            for p, m in current_mtimes.items():
                if p not in last_mtimes or m > last_mtimes[p]:
                    changed_file = p
                    break
            
            # Detect deleted files
            if not changed_file:
                for p in last_mtimes:
                    if p not in current_mtimes:
                        changed_file = p
                        break
                        
            if changed_file:
                print(f"\n[{time.strftime('%H:%M:%S')}] Detected change in {os.path.basename(changed_file)}. Restarting application...")
                
                # Terminate the current running application
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                
                # Relaunch the application
                proc = subprocess.Popen(cmd)
                last_mtimes = current_mtimes
    except KeyboardInterrupt:
        print("\nStopping Hot-Reload runner.")
        if proc.poll() is None:
            proc.terminate()

if __name__ == "__main__":
    main()
