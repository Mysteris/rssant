import datetime
import time
from base64 import urlsafe_b64encode, urlsafe_b64decode

from validr import T, validator, SchemaError, Invalid, Compiler
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .helper import coerce_url
from .cursor import Cursor


def pagination(item):
    return T.dict(
        previous=T.cursor.optional,
        next=T.cursor.optional,
        total=T.int.optional,
        size=T.int.optional,
        results=T.list(item)
    )


@validator(accept=(str, object), output=(str, object))
def cursor_validator(compiler, keys=None, output_object=False, base64=False):
    """Cursor: k1:v1,k2:v2"""
    if keys:
        try:
            keys = set(keys.strip().replace(',', ' ').split())
        except (TypeError, ValueError):
            raise SchemaError('invalid cursor keys')

    def validate(value):
        try:
            if not isinstance(value, Cursor):
                if base64:
                    value = urlsafe_b64decode(value.encode('ascii')).decode('utf-8')
                value = Cursor.from_string(value, keys)
            else:
                value._check_missing_keys(keys)
        except (UnicodeEncodeError, UnicodeDecodeError, ValueError) as ex:
            raise Invalid(str(ex)) from None
        if output_object:
            return value
        value = str(value)
        if base64:
            value = urlsafe_b64encode(value.encode('utf-8')).decode()
        return value

    return validate


@validator(accept=str, output=str)
def url_validator(compiler, schemes='http https', default_schema=None):
    """
    Args:
        default_schema: 接受没有scheme的url并尝试修正
    """
    schemes = set(schemes.replace(',', ' ').split(' '))
    _django_validate_url = URLValidator(schemes=schemes)
    if default_schema and default_schema not in schemes:
        raise SchemaError('invalid default_schema {}'.format(default_schema))

    def validate(value):
        if default_schema:
            value = coerce_url(value, default_schema=default_schema)
        try:
            _django_validate_url(value)
        except ValidationError as ex:
            raise Invalid(','.join(ex.messages).rstrip('.'))
        return value

    return validate


@validator(accept=(str, object), output=(str, object))
def datetime_validator(compiler, format='%Y-%m-%dT%H:%M:%S.%fZ', output_object=False):
    def validate(value):
        try:
            if isinstance(value, list) and len(value) == 9:
                value = tuple(value)
            if isinstance(value, tuple):
                value = datetime.datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
            elif not isinstance(value, datetime.datetime):
                value = parse_datetime(value)
                if value is None:
                    raise ValueError('not well formatted at all')
            if not timezone.is_aware(value):
                value = timezone.make_aware(value, timezone=timezone.utc)
            if output_object:
                return value
            else:
                return value.strftime(format)
        except Exception as ex:
            raise Invalid('invalid datetime') from ex
    return validate


VALIDATORS = {
    'cursor': cursor_validator,
    'url': url_validator,
    'datetime': datetime_validator,
}


compiler = Compiler(validators=VALIDATORS)
