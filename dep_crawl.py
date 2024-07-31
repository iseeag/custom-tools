import ast
from types import ModuleType, FunctionType, MethodType

from pydantic import BaseModel
from typing import Optional, List
import inspect
from pathlib import Path


class Import(BaseModel):
    stmt: str
    module: Optional[str] = None
    obj: str


def extract_imports(file_path) -> List[Import]:
    with open(file_path, 'r') as file:
        tree = ast.parse(file.read(), filename=file_path)

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                stmt = f"import {alias.name}"
                imports.append(Import(stmt=stmt, obj=alias.name))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                stmt = f"from {node.module} import {alias.name}"
                imports.append(Import(stmt=stmt, module=node.module, obj=alias.name))

    return imports


def get_module_src_file(imp: Import) -> str | None:
    states = {}
    stmt = f"import {imp.module}"
    exec(stmt, states)
    mod_name, *rest = imp.module.split('.')
    from functools import reduce
    value = reduce(getattr, rest, states[mod_name])
    return inspect.getfile(value)


def get_src_file(imp: Import) -> str | None:
    print(imp)
    states = {}
    exec(imp.stmt, states)
    if isinstance(states[imp.obj], (ModuleType, FunctionType, MethodType)) or inspect.isclass(states[imp.obj]):
        return inspect.getfile(states[imp.obj])
    if isinstance(states[imp.obj], (int, float, str, list, dict, tuple)):
        return get_module_src_file(imp)


def is_sub_path(path: str, bound_path: str) -> bool:
    return Path(path).resolve().is_relative_to(Path(bound_path).resolve())


def get_src_file_rec(file: str, bound_path: str) -> List[str]:
    if not is_sub_path(file, bound_path):
        return []
    imports = extract_imports(file)
    src_files = []
    for imp in imports:
        if (src_file := get_src_file(imp)) is not None:
            if not is_sub_path(src_file, bound_path):
                continue
            src_files.append(src_file)
            src_files.extend(get_src_file_rec(src_file, bound_path))
    return list(set(src_files))
