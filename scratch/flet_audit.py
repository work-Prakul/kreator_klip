import flet
import os
import sys

search_terms = [
    'FilePickerResultEvent', 
    'NavigationRailLabelType', 
    'FontWeight', 
    'ThemeMode', 
    'TextOverflow', 
    'MainAxisAlignment', 
    'CrossAxisAlignment',
    'FontWeight',
    'margin'
]

flet_dir = os.path.dirname(flet.__file__)
results = {}

print(f"Searching in: {flet_dir}")

for root, dirs, files in os.walk(flet_dir):
    for file in files:
        if file.endswith('.py') or file.endswith('.pyi'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for term in search_terms:
                        if term in content:
                            if term not in results:
                                results[term] = []
                            # Convert file path to module path
                            rel_path = os.path.relpath(path, flet_dir)
                            mod_path = rel_path.replace(os.path.sep, '.').replace('.pyi', '').replace('.py', '').replace('.__init__', '')
                            full_mod = f"flet.{mod_path}" if mod_path != "." else "flet"
                            results[term].append(full_mod)
            except Exception as e:
                pass

print("\n--- SEARCH RESULTS ---")
for term, paths in results.items():
    print(f"{term}: {list(set(paths))}")

print("\n--- VERSION INFO ---")
print(f"Flet Version: {getattr(flet, '__version__', 'unknown')}")
