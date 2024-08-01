import os

from mockeries.mock_module import abc
from mockeries.sub_mod import dummy
from mockeries.sub_mod.dummy import dummy_func

if __name__ == '__main__':
    dummy_func()
    abc()
