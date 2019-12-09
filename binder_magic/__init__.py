"""Binder magic"""

from .binder_magic import BinderMagic

def load_ipython_extension(ipython):
    ipython.register_magics(BinderMagic)
