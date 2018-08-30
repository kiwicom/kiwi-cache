"""Utility functions."""
import time


def get_current_timestamp():
    # type: () -> float
    """Get current timestamp float value."""
    return time.time()


def mandatory_validator(instance, attribute, value):
    """Validator for mandatory attribute."""
    if not value:
        raise AttributeError("{} is mandatory".format(attribute))
