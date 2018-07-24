"""Utility functions."""

import arrow


def get_current_timestamp():
    # type: () -> int
    """Get current timestamp int value."""
    return arrow.utcnow().timestamp


def mandatory_validator(instance, attribute, value):
    """Validator for mandatory attribute."""
    if not value:
        raise AttributeError("{} is mandatory".format(attribute))
