import math as math


def abc(*args, **kwargs):
    return 1


def add_func(x: int, y: int, *args, k=0, **kwargs) -> int:
    import math
    math.log(3)
    x = 1
    a, b = 1, 2

    def cde(x):
        return x

    abc(**kwargs)
    # return x + y + sum(args) + k + sum(kwargs.values())
    return x + y


class A:
    def __init__(self, a=0):
        self.a = a

    def p(self, b=3):
        return self.a + b

    @staticmethod
    def s(a, b):
        return a + b

    @classmethod
    def from_int(cls, a):
        return cls(a)


class B:
    def __init__(self):
        self.a = A()


class C(A):
    def __init__(self):
        super().__init__()

    def q(self, b=3):
        out = super().p(b)
        return out

    def q1(self, b=3):
        out = A.p(self, b)
        return out
