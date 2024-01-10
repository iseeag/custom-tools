import ast
import inspect
import textwrap
from typing import List

import ipdb
from icecream import Source, callOrValue, ic


def find_variable_name(var, global_ctx: dict):
    for name, value in global_ctx.items():
        if value is var:
            return name
    return None


def parse_obj_to_ast_node(obj, global_ctx: dict = None):
    if isinstance(obj, (int, float, str, bool)):
        return ast.Constant(value=obj)
    elif var_name := find_variable_name(obj, global_ctx or {}):
        return ast.Name(id=var_name, ctx=ast.Load())
    elif isinstance(obj, list):
        return ast.List(elts=[parse_obj_to_ast_node(item) for item in obj])
    elif isinstance(obj, dict):
        return ast.Dict(keys=[parse_obj_to_ast_node(k) for k in obj.keys()],
                        values=[parse_obj_to_ast_node(v) for v in obj.values()])
    elif isinstance(obj, tuple):
        return ast.Tuple(elts=[parse_obj_to_ast_node(item) for item in obj])
    elif isinstance(obj, set):
        return ast.Set(elts=[parse_obj_to_ast_node(item) for item in obj])
    elif isinstance(obj, type(None)):
        return ast.Constant(value=None)
    elif isinstance(obj, ast.AST):
        return obj
    else:
        raise NotImplementedError(f'obj type {type(obj)} cannot be parsed to ast node')


def expand_kwargs(node: ast.Name, global_ctx: dict):
    var_name = node.id
    var = global_ctx.get(var_name)
    assert isinstance(var, dict)
    kwargs = {k: parse_obj_to_ast_node(v, global_ctx) for k, v in var.items()}
    return kwargs


def expand_args(node: ast.Name, global_ctx: dict):
    var_name = node.id
    var = global_ctx.get(var_name)
    assert isinstance(var, (list, tuple))
    args = [parse_obj_to_ast_node(v, global_ctx) for v in var]
    return args


def unpack_call(call_frame, debug=False):
    callNode = Source.executing(call_frame).node

    call = callNode.args[0]
    if isinstance(call.func, ast.Name):  # function call
        func_name = call.func.id
        func = call_frame.f_globals.get(func_name)
        method_ptr = None

        if not hasattr(func, '__name__'):  # handle __call__ case of method call
            # func = func.__call__
            func_instance, func = func, func.__call__
            method_ptr = {'instance_name': func_name,
                          'instance_ref': parse_obj_to_ast_node(func_instance, call_frame.f_globals),
                          'method_name': func_name + '_call',
                          'instance_type': type(func_instance),
                          'super_class_name': func_instance.__class__.__bases__[0].__name__}

    elif isinstance(call.func, ast.Attribute):  # method call
        method_name = call.func.attr
        attr_list = []
        func_val = call.func.value
        while not isinstance(func_val, ast.Name):
            attr_list.append(func_val.attr)
            func_val = func_val.value
        attr_list.append(func_val.id)
        instance_name = attr_list.pop()
        instance = call_frame.f_globals.get(instance_name)
        while attr_list:
            instance_name = attr_list.pop()
            instance = getattr(instance, instance_name)

        func = getattr(instance, method_name)
        method_ptr = {'instance_name': instance_name,
                      'instance_ref': call.func.value,
                      'method_name': method_name,
                      'instance_type': type(instance),
                      'super_class_name': instance.__class__.__bases__[0].__name__}
    else:
        raise NotImplementedError

    args = []
    for arg in call.args:
        if debug:
            ic(arg)
        if isinstance(arg, ast.Starred):
            expanded_args = expand_args(arg.value, call_frame.f_globals)
            args.extend(expanded_args)
        else:
            args.append(callOrValue(arg))

    kwargs = {}
    for kw in call.keywords:
        if debug:
            ic(kw.arg, kw.value)
        if kw.arg is None and isinstance(kw.value, ast.Name):
            expanded_kwargs = expand_kwargs(kw.value, call_frame.f_globals)
            kwargs = kwargs | expanded_kwargs
        else:
            kwargs[kw.arg] = callOrValue(kw.value)

    return func, args, kwargs, method_ptr


def get_argument_map(func, args, kwargs, method_ptr, unparsed=False, debug=False):
    if debug:
        ic(args, kwargs)

    if unparsed:
        post_argument_map = inspect.getcallargs(
            func,
            *[ast.unparse(arg) for arg in args],
            **{k: ast.unparse(v) for k, v in kwargs.items()}
        )
        return post_argument_map

    argument_map = inspect.getcallargs(func, *args, **kwargs)
    ic(argument_map)
    post_argument_map = {}
    for k, v in argument_map.items():
        if method_ptr and isinstance(v, method_ptr['instance_type']):
            post_argument_map[k] = method_ptr['instance_ref']
            method_ptr['instance_self_ref_name'] = k
        elif isinstance(v, (ast.AST, tuple, dict)):
            post_argument_map[k] = v
        else:
            obj_ast = parse_obj_to_ast_node(v)
            post_argument_map[k] = obj_ast

    return post_argument_map, method_ptr


def count_trailing_underscores(var_name):
    stripped_var_name = var_name.rstrip('_')
    return len(var_name) - len(stripped_var_name)


class VariableRenameTransformer(ast.NodeTransformer):
    def __init__(self, old_name, new_name):
        self.old_name = old_name
        self.new_name = new_name

    def visit_Name(self, node):
        if node.id == self.old_name:
            node.id = self.new_name
        return self.generic_visit(node)


class VariableNodeTransformer(ast.NodeTransformer):
    def __init__(self, var_name: str, new_node: ast.AST):
        self.var_name = var_name
        self.new_node = new_node

    def visit_Name(self, node):
        if node.id == self.var_name:
            self.new_node.ctx = node.ctx
            return self.new_node
        return self.generic_visit(node)


class ReturnToAssignmentTransformer(ast.NodeTransformer):
    def __init__(self, ret_var_name='ret'):
        self.ret_var_name = ret_var_name

    def visit_Return(self, node):
        if node.value:
            new_assignment = ast.Assign(
                targets=[ast.Name(id=self.ret_var_name, ctx=ast.Store())],
                value=node.value
            )
            return ast.copy_location(new_assignment, node)
        return node


class SuperCallTransformer(ast.NodeTransformer):
    def __init__(self, instance_self_ref_name, super_class_name):
        self.ancestor_stack = []
        self.instance_self_ref_name = instance_self_ref_name
        self.super_class_name = super_class_name

    def generic_visit(self, node):
        self.ancestor_stack.append(node)
        super().generic_visit(node)
        self.ancestor_stack.pop()
        return node

    def visit_Call(self, node: ast.Call):
        if hasattr(node.func, 'id') and node.func.id == 'super':
            # parent: ast.Attribute = self.ancestor_stack[-1]
            # parent.value = ast.Name(id=self.super_class_name, ctx=ast.Load())
            grandparent: ast.Call = self.ancestor_stack[-2]
            grandparent.args.insert(0, ast.Name(id=self.instance_self_ref_name, ctx=ast.Load()))
            return ast.Name(id=self.super_class_name, ctx=ast.Load())
        return self.generic_visit(node)


def replace_return_with_assignment(func_ast: ast.AST, ret_var_name='ret'):
    if not isinstance(func_ast, ast.FunctionDef):
        raise TypeError('func_ast must be a FunctionDef')
    body = func_ast.body
    ret_nodes = [node for node in body if isinstance(node, ast.Return)]
    if ret_nodes:
        ret_node = ret_nodes[0]
        ret_node_idx = body.index(ret_node)
        if ret_node.value:
            new_assignment = ast.Assign(
                targets=[ast.Name(id=ret_var_name, ctx=ast.Store())],
                value=ret_node.value
            )
            body.insert(ret_node_idx, ast.copy_location(new_assignment, ret_node))
            body.remove(ret_node)
    else:
        return


def extrac_arg_names(argument_map: dict) -> List[str]:
    arg_names = []
    for arg_name, val in argument_map.items():
        if isinstance(val, tuple):
            for node in val:
                for node in ast.walk(node):
                    if isinstance(node, ast.Name):
                        arg_names.append(node.id)
        elif isinstance(val, dict):
            for node in val.values():
                for node in ast.walk(node):
                    if isinstance(node, ast.Name):
                        arg_names.append(node.id)
        elif isinstance(val, ast.Constant):
            continue
        else:
            for node in ast.walk(val):
                if isinstance(node, ast.Name):
                    arg_names.append(node.id)
    return list(set(arg_names))


def swap_var_names(func_def: ast.FunctionDef, argument_map: dict, pre_swap: dict):
    for arg_name, val in argument_map.items():
        new_var = pre_swap.get(arg_name, arg_name)
        if isinstance(val, ast.AST):
            func_def.body.insert(
                0, ast.parse(f'{new_var} = {ast.unparse(val)}'))
            continue

        if isinstance(val, ast.Name):
            new_var = pre_swap.get(arg_name, arg_name)
            if arg_name == val.id:
                continue
            func_def.body.insert(
                0, ast.parse(f'{new_var} = {val.id}'))

        if isinstance(val, tuple):  # args case
            func_def.body.insert(
                0, ast.parse(f'{new_var} = {ast.unparse(ast.Tuple(elts=val))}'))
            continue

        if isinstance(val, dict):  # kwargs case
            dict_ast = ast.Dict(keys=[ast.Constant(k) for k in val.keys()],
                                values=[v for v in val.values()])
            func_def.body.insert(
                0, ast.parse(f'{new_var} = {ast.unparse(dict_ast)}'))
            continue


def refresh_var_names(func_ast: ast.AST, arg_names: List[str]):
    var_to_new_var = {}
    for arg_name in arg_names:
        base_underscore_count = count_trailing_underscores(arg_name)
        existing_underscore_counts = [count_trailing_underscores(node.id) - base_underscore_count
                                      for node in ast.walk(func_ast)
                                      if isinstance(node, ast.Name) and arg_name in node.id]
        if existing_underscore_counts:
            min_underscore_count = min(set(range(1, 100)) - set(existing_underscore_counts))
            new_var_name = arg_name + '_' * min_underscore_count
            avoid_arg_name = VariableRenameTransformer(arg_name, new_var_name)
            avoid_arg_name.visit(func_ast)
            # func_ast: ast.Module =
            var_to_new_var[arg_name] = new_var_name
    return var_to_new_var


class VariableCollector(ast.NodeVisitor):
    def __init__(self):
        self.defined = set()  # Set of defined variables
        self.used = set()  # Set of used variables

    def visit_FunctionDef(self, node):
        for arg in node.args.args:
            self.defined.add(arg.arg)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined.add(target.id)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.defined.add(alias.name if alias.asname is None else alias.asname)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.defined.add(alias.name if alias.asname is None else alias.asname)

    def visit_For(self, node):
        if isinstance(node.target, ast.Name):
            self.defined.add(node.target.id)
        self.generic_visit(node)

    def visit_While(self, node):
        if isinstance(node.target, ast.Name):
            self.defined.add(node.target.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)
        self.generic_visit(node)


class VariableStatmentCollector(ast.NodeVisitor):
    def __init__(self, skip_func_def=None):
        self.import_lst = []
        self.assignment_lst = []
        self.definition_lst = []
        self.skip_func_def = skip_func_def

    def visit_FunctionDef(self, node):
        for arg in node.args.args:
            self.defined.add(arg.arg)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined.add(target.id)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.defined.add(alias.name if alias.asname is None else alias.asname)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)
        self.generic_visit(node)


def extract_import(func_ast, module_ast, call_frame=None):
    """
    1. find undefined var in scope
    2. search import / definition / assignment in module for the var before the func
    3. return import statement
    *4. if var is still undefined, log error
    """
    if not call_frame:
        call_frame = inspect.currentframe().f_back
    var_collector = VariableCollector()
    var_collector.visit(func_ast)
    undefined_vars = list(var_collector.used - var_collector.defined)
    undefined_vars = [var for var in undefined_vars
                      if not hasattr(call_frame.f_globals['__builtins__'], var)]
    ic(undefined_vars)
    return call_frame


def inline_src(called, debug=False):
    """
    It does not work in situation where callframe isn't available! e.g. repl from commandline

    1. get func/method and call args
    2. rename vars in func/method to avoid conflicts
        a. get all name from args and kwargs
        b. check and get var_to_new_var map
    3. swap variable names, append input if needed
        a. map var to new var
        b. modify accordingly:
            - val is a constant, add assignment to the beginning of the function
            - var and val are equal in terms of var name, if yes skip
            - val is a list, unparse list, add assignment to the beginning of the function
            - val is a dict, unparse dict, add assignment to the beginning of the function
    4. track any var in the function that was undefined in scope
        - find the last assignment/import/definition of the var in the module:
            - it comes from an import, add import to the beginning of the function
            - it comes from a definition/assignment, then add import to the beginning of the function
            - report error if var is still undefined
        - collect all the vars that were still undefined
    4. print arguments, old func, code and imports
    """
    # Get func/method and call args
    callFrame = inspect.currentframe().f_back
    func, args, kwargs, method_ptr = unpack_call(callFrame)
    argument_map, method_ptr = get_argument_map(func, args, kwargs, method_ptr)
    input_arguments = get_argument_map(func, args, kwargs, method_ptr, unparsed=True)
    if debug:
        ic(argument_map)
    ic(input_arguments)

    # Get source code
    src = inspect.getsource(func)
    dedented_src = textwrap.dedent(src)
    func_ast = ast.parse(dedented_src)
    new_func_ast: ast.Module = ast.parse(dedented_src)
    if debug:
        print('# ------------------------ original ast: ')
        print(ast.dump(func_ast, indent=4))

    print('# ------------------------ original def: ')
    # code = ast.unparse(func_ast)
    # print(code)
    print(src)

    # Get all names from args and kwargs
    arg_names = extrac_arg_names(argument_map)
    ic(arg_names)

    # Rename vars in func/method to avoid conflicts
    var_to_new_var = refresh_var_names(new_func_ast, arg_names)
    ic(var_to_new_var)

    if method_ptr and 'instance_self_ref_name' in method_ptr:
        self_rename = VariableNodeTransformer(method_ptr['instance_self_ref_name'],
                                              method_ptr['instance_ref'], )
        self_rename.visit(new_func_ast)
        argument_map.pop(method_ptr['instance_self_ref_name'])

    # Swap variable names, append input if needed
    new_func_def: ast.FunctionDef = new_func_ast.body[0]
    swap_var_names(new_func_def, argument_map, var_to_new_var)

    # module_file_path = inspect.getsourcefile(func)
    # with open(module_file_path, 'r') as file:
    #     module_source = file.read()
    # module_ast = ast.parse(module_source)
    # print(ast.dump(module_ast, indent=4))
    # new_code = ast.unparse(new_func_ast)

    ret_var_name = (method_ptr['method_name'] if method_ptr else new_func_def.name) + '_ret'
    replace_return_with_assignment(new_func_def, ret_var_name)
    if method_ptr:  # handle super() call inside method
        SuperCallTransformer(method_ptr['instance_name'],
                             method_ptr['super_class_name']).visit(new_func_ast)

    if debug:
        print('# ------------------------ new ast: ')
        print(ast.dump(new_func_ast, indent=4))
    new_code = ast.unparse(new_func_def.body)
    print('# ------------------ inlined code block:')
    print(new_code)
    print('# --------------------------------------')

    if debug:
        return argument_map, func_ast, new_func_ast
    else:
        return called


if __name__ == '__main__':
    import ast
    import inspect

    from icecream import Source, ic

    from ast_inline import VariableCollector, extract_import, inline_src
    from mockeries.mock_module import A, B, add_func

    x = 1
    y = 2
    z = 'rr'
    argument_map, func_ast, new_func_ast = inline_src(add_func([1], x, 1, 2, 3, k={3: 4}, z=z), debug=True)
    # argument_map, func_ast, new_func_ast = inline_src(add_func(1, 1), debug=True)
    inline_src(add_func(1, 1))

    b = B()
    a = A()
    ic(b.a.p(1))
    argument_map, func_ast, new_func_ast = inline_src(a.p(2), debug=True)

    print(ast.dump(func_ast, indent=4))
    print(ast.unparse(func_ast))
