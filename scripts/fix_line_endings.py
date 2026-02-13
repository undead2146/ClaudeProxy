#!/usr/bin/env python3
import os
import sys

def to_lf(path):
    with open(path, 'rb') as f:
        content = f.read()

    # Replace CRLF with LF, and also isolated CR with LF just in case
    new_content = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')

    if new_content != content:
        print(f"Fixing line endings for: {path}")
        with open(path, 'wb') as f:
            f.write(new_content)
        return True
    return False

def main():
    # Fix scripts directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    files_to_fix = []

    # Scan scripts dir
    for f in os.listdir(script_dir):
        if f.endswith('.sh') or f.endswith('.py'):
            files_to_fix.append(os.path.join(script_dir, f))

    # Scan server dir
    server_dir = os.path.join(project_root, 'server')
    if os.path.exists(server_dir):
        for root, dirs, files in os.walk(server_dir):
            for f in files:
                if f.endswith('.py') or f.endswith('.sh'):
                    files_to_fix.append(os.path.join(root, f))

    count = 0
    for file_path in files_to_fix:
        try:
            if to_lf(file_path):
                count += 1
                # Also ensure executable
                if file_path.endswith('.sh'):
                    st = os.stat(file_path)
                    os.chmod(file_path, st.st_mode | 0o111)
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    print(f"Fixed line endings for {count} files.")

if __name__ == "__main__":
    main()
