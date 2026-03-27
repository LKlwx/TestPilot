import os

# 这里面的文件夹 & 文件都会自动忽略
IGNORE = {
    "__pycache__", ".git", ".idea", ".vscode",
    "venv", "env", ".pytest_cache", "dist", "build",
    ".pyc", ".pyo", ".pyd"
}


def tree(path, prefix=""):
    names = sorted(os.listdir(path), key=lambda s: s.lower())
    items = []
    for name in names:
        if name in IGNORE or any(name.endswith(ext) for ext in IGNORE):
            continue
        items.append(name)

    for i, name in enumerate(items):
        full = os.path.join(path, name)
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        print(prefix + connector + name)
        if os.path.isdir(full):
            new_prefix = prefix + ("    " if is_last else "│   ")
            tree(full, new_prefix)


if __name__ == "__main__":
    tree(".")
