from __future__ import absolute_import, print_function

import datetime
from decimal import Decimal
import enum
from functools import partial
import json
import time
from typing import Any, List, Tuple, Union  # pylint: disable=unused-import

import attr
import simplejson


def default_encoder(obj):  # pylint: disable=method-hidden
    """Default encoder used for dumps function."""
    if isinstance(obj, Decimal):
        return str(float(obj))

    if hasattr(obj, 'isoformat'):  # handles both date and datetime objects
        return str(obj)

    if isinstance(obj, set):
        return list(obj)

    if isinstance(obj, enum.Enum):
        return obj.name

    try:
        # attrs objects can appear when logging stuff
        return attr.asdict(obj, dict_factory=masked_dict)
    except attr.exceptions.NotAnAttrsClassError:
        pass

    try:
        obj_dict = obj.asdict()
    except AttributeError:
        pass
    else:
        return masked_dict(list(obj_dict.items()))

    raise TypeError(repr(obj) + " is not JSON serializable")


def masked_dict(data=None):
    # type: (Union[List[Tuple[Any, Any]], dict, None]) -> dict
    """Return a dict with dangerous looking key/value pairs masked."""
    if not data:
        return dict()
    if isinstance(data, dict):
        data = data.items()

    blacklist = {'secret', 'token', 'password', 'key'}
    whitelist = {'booking_token', 'public_key', 'idempotency_key'}

    return {
        key:
        ('-- MASKED --' if key.lower() not in whitelist and any(word in key.lower() for word in blacklist) else value)
        for key, value in data
    }


def json_encoder(obj):
    """Convert datetime objects into timestamp."""
    if isinstance(obj, datetime.datetime):
        return time.mktime(obj.timetuple())
    elif isinstance(obj, datetime.timedelta):
        return obj.total_seconds()


def jsonify(obj):
    """Try to convert python object to encodable by default encoder.

    :param obj: Python object to convert
    """
    return json.loads(json.dumps(obj, default=default_encoder))


loads = simplejson.loads
dumps = partial(simplejson.dumps, default=default_encoder)
