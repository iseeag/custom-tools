import ast
import inspect

from icecream import Source, ic

from ast_inline import VariableCollector, extract_import, inline_src
from mockeries.mock_module import A, B, add_func

# ------- test function
x = 1
y = 2
z = 'rr'
argument_map, func_ast, new_func_ast = inline_src(add_func([1], x, 1, 2, 3, k={3: 4}, z=z), debug=True)
# argument_map, func_ast, new_func_ast = inline_src(add_func(1, 1), debug=True)
inline_src(add_func(1, 1))

# ------- test instance method
a = A()
argument_map, func_ast, new_func_ast = inline_src(a.p(2), debug=True)

# ------- test chained attribute class method
b = B()
ic(b.a.p(1))
argument_map, func_ast, new_func_ast = inline_src(b.a.p(2), debug=True)

# ------ test static method
inline_src(a.s(2, 3))

# ------ test class method
inline_src(A.from_int(5))

print(ast.dump(func_ast, indent=4))
print(ast.unparse(func_ast))

# todo:
#  1. handle super()
#  1a. handle calling method from uninitialized class
#  2. handle __call__
#  3. handle empty dict **kwargs
#  4. handle *args generate var = *args erroneous syntax, also check for **kwargs
