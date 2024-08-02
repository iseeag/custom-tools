import ast
import inspect
import os
import sys
from functools import reduce
from pathlib import Path
from types import FunctionType, MethodType, ModuleType
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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


def is_builtin_module(module_name):
    return module_name in sys.builtin_module_names


def get_value_from_state_dict(ref: str, state_dict: Dict) -> Any:
    mod_name, *rest = ref.split('.')
    value = reduce(getattr, rest, state_dict[mod_name])
    return value


def get_module_src_file(imp: Import) -> str | None:
    states = {}
    stmt = f"import {imp.module}"
    exec(stmt, states)
    value = get_value_from_state_dict(imp.module, states)
    return inspect.getfile(value)


def get_src_file(imp: Import) -> str | None:
    states = {}
    exec(imp.stmt, states)
    obj = get_value_from_state_dict(imp.obj, states)
    if isinstance(obj, (ModuleType, FunctionType, MethodType)) or inspect.isclass(obj):
        if is_builtin_module(imp.obj):
            return
        return inspect.getfile(obj)
    if isinstance(obj, (int, float, str, list, dict, tuple)):
        return get_module_src_file(imp)


def is_sub_path(path: str, bound_path: str, is_abs=False) -> bool:
    if is_abs:
        return Path(path).is_relative_to(Path(bound_path))
    else:
        return Path(path).resolve().is_relative_to(Path(bound_path).resolve())


def to_relative_path(abs_path) -> str:
    current_working_directory = os.getcwd()
    relative_path = os.path.relpath(abs_path, current_working_directory)
    return relative_path


def get_src_files_rec(file: str, bound_path: str = '.', extracted: List[str] = None, is_abs=False) -> List[str]:
    if extracted is None:
        extracted = []
    if not is_sub_path(file, bound_path, is_abs):
        return []
    imports = extract_imports(file)
    src_files = []
    for imp in imports:
        if (src_file := get_src_file(imp)) is not None:
            if not is_sub_path(src_file, bound_path, is_abs):
                continue
            if src_file not in src_files + extracted:
                src_files.append(src_file)
    extracted = list(set(src_files + extracted))
    final_src_files = []
    for src_file in src_files:
        sub_src_files = get_src_files_rec(src_file, bound_path, extracted, is_abs)
        final_src_files.extend(sub_src_files)
    return list(set(final_src_files + extracted))


def get_src_files(file: str, bound_path: str = '.', is_abs=False) -> List[str]:
    files = get_src_files_rec(file, bound_path, [], is_abs)
    if is_abs:
        return files
    return [to_relative_path(file) for file in files]
