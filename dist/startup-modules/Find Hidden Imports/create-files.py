import os
import sys
from fnmatch import fnmatch

# Resolve the project root regardless of where this script is run from.
# When called from build.bat the cwd is the script's own directory.
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))

out_path = os.path.join(project_root, 'files.py')

# Open in write mode ('w') so repeated builds don't accumulate stale imports.
file = open(out_path, 'w')

pattern = "*.py"
# Skip __init__ modules (written as package-only imports below) and
# anything inside the dist/ or build/ folders.
no_include = ['__init__', 'import dist.', 'import build.', 'import .venv.']

def walk_package(root, import_prefix):
    for path, subdirs, filenames in os.walk(root):
        # Skip hidden dirs, dist/, build/, venv
        subdirs[:] = [d for d in subdirs
                      if not d.startswith('.') and d not in ('dist', 'build', '__pycache__')]
        for name in filenames:
            if not fnmatch(name, pattern):
                continue
            full = os.path.join(path, name)
            rel = os.path.relpath(full, os.path.dirname(root))
            import_line = 'import ' + rel.replace('.py', '').replace(os.sep, '.')
            if any(excl in import_line for excl in no_include):
                # For __init__ files just import the package itself
                if '__init__' in import_line:
                    pkg = import_line.replace('.__init__', '')
                    print(pkg)
                    file.write(pkg + '\n')
                continue
            print(import_line)
            file.write(import_line + '\n')

# Walk toontown and otp source trees
for package in ('toontown', 'otp'):
    pkg_dir = os.path.join(project_root, package)
    if os.path.isdir(pkg_dir):
        walk_package(pkg_dir, package)

# Walk direct from Nuitka-Python if present (optional — not required for a working build)
nuitka_direct = os.path.join(project_root, 'Nuitka-Python', 'output', 'Lib',
                              'site-packages', 'direct')
if os.path.isdir(nuitka_direct):
    walk_package(nuitka_direct, 'direct')
else:
    # Fall back to the venv's direct package
    venv_direct = os.path.join(project_root, '.venv', 'Lib', 'site-packages', 'direct')
    if os.path.isdir(venv_direct):
        walk_package(venv_direct, 'direct')

file.close()
print(f'\nWrote {out_path}')