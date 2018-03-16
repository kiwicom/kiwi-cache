class ReadOnlyDictMixin(object):
    """Add to a ``collections.UserDict`` to make it read-only."""

    def raise_readonly_error(self, *_, **__):
        raise RuntimeError('This dictionary is read-only')

    __setitem__ = __delitem__ = pop = popitem = clear = update = setdefault = raise_readonly_error


class CallAttemptException(Exception):

    def __init__(self, name):
        super(CallAttemptException, self).__init__("Max attempt of call {}".format(name))


class CallAttempt():

    def __init__(self, name, max_call=3):
        self.counter = None
        self.name = name
        self.max_call = max_call
        self.reset()

    def countdown(self):
        # infinity loop is allow when max_call is set to -1
        if self.max_call < 0:
            return
        self.counter -= 1
        if self.counter < 1:
            raise CallAttemptException(self.name)

    def reset(self):
        self.counter = self.max_call
