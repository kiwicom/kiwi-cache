import attr


class ReadOnlyDictMixin(object):
    """Add to a ``collections.UserDict`` to make it read-only."""

    def raise_readonly_error(self, *_, **__):
        raise RuntimeError("This dictionary is read-only")

    __setitem__ = __delitem__ = pop = popitem = clear = update = setdefault = raise_readonly_error


class CallAttemptException(Exception):
    def __init__(self, name):
        super(CallAttemptException, self).__init__("Max attempt of call {}".format(name))


@attr.s
class CallAttempt(object):

    name = attr.ib(None, type=str)
    max_attempts = attr.ib(3, type=int)
    counter = attr.ib(None, type=int)

    def __attrs_post_init__(self):
        self.reset()

    def countdown(self):
        # infinity loop is allow when max_call is set to -1
        if self.max_attempts < 0:
            return
        self.counter -= 1
        if self.counter < 1:
            self.reset()
            raise CallAttemptException(self.name)

    def reset(self):
        self.counter = self.max_attempts
