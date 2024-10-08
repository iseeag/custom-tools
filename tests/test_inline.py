import ast
import inspect

from icecream import Source, ic

from ast_inline import VariableCollector, extract_import, inline_src
from mockeries.mock_module import A, B, C, add_func

# ------- test function
x = 1
y = 2
z = 'rr'
inline_src(add_func(1, 1))
inline_src(add_func([1], x, 1, 2, 3, k={3: 4}, z=z))

# ------- test function with *args and **kwargs
some_args = (1, 2, 3)
inline_src(add_func(1, *some_args))

some_kwargs = {'k': 9, 'b': 3}
inline_src(add_func(1, 2, **some_kwargs))

inline_src(add_func(*some_args, **some_kwargs))
# ------- test instance method
a = A()
inline_src(a.p(2))

# ------- test chained attribute class method
b = B()
ic(b.a.p(1))
argument_map, func_ast, new_func_ast = inline_src(b.a.p(2), debug=True)

# ------ test static method
inline_src(a.s(x, 3))

# ------ test class method
inline_src(A.from_int(5))

# ------ test class method from uninitiated class
inline_src(A.p(a, 5))

# ------ test super()
c = C()
inline_src(c.q(5))
inline_src(c.q1(5))

# ------ test __call__
inline_src(b.__call__())
inline_src(b())

print(ast.dump(func_ast, indent=4))
print(ast.unparse(func_ast))

# todo:
#  1. add import statements by checking unbound names
