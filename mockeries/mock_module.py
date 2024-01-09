import math as math


def abc(*args, **kwargs):
    return 1


def add_func(x: int, y: int, *args, k=0, **kwargs) -> int:
    import math
    math.log(3)
    x = 1
    a, b = 1, 2
    abc(**kwargs)
    # return x + y + sum(args) + k + sum(kwargs.values())
    return x + y


class A:
    def __init__(self):
        self.a = 1

    def p(self):
        print(self.a)
