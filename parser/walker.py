import ast
import sys
from pathlib import Path
from parser.visitor import collect_defined_names, CallGraphVisitor, collect_imports

def walk_repo(repo_path: str):
    path = Path(repo_path)
    all_edges = []
    skip = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".pytest_cache",}

    def path_to_module(file_path, repo_root):
        relative = file_path.relative_to(repo_root).as_posix()
        return relative.replace("/", ".").removesuffix(".py")

    # build once before the loop
    repo_modules = set()
    for file_path in path.rglob("*.py"):
        if any(part in skip for part in file_path.parts):
            continue
        repo_modules.add(path_to_module(file_path, path))

    for file_path in path.rglob("*.py"):
        if any(part in skip for part in file_path.parts):
            continue
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            print(f"Skipping {file_path}: {e}")
            continue
        defined_names = collect_defined_names(tree)
        imports = collect_imports(tree)
        visitor = CallGraphVisitor(defined_names, imports, repo_modules)
        visitor.visit(tree)

        for edge in visitor.edges:
            relative_path = file_path.relative_to(path).as_posix()
            qualified_caller = f"{relative_path}:{edge[0]}"
            all_edges.append((qualified_caller, edge[1], edge[2], edge[3]))

    return all_edges


