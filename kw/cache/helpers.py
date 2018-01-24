class ReadOnlyDictMixin(object):
    """Add to a ``collections.UserDict`` to make it read-only."""

    def raise_readonly_error(self, *_, **__):
        raise RuntimeError('This dictionary is read-only')

    __setitem__ = __delitem__ = pop = popitem = clear = update = setdefault = raise_readonly_error
