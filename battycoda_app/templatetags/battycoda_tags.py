from itertools import groupby

from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary by key

    Usage:
        {{ my_dict|get_item:key_var }}
    """
    return dictionary.get(key, "")


@register.filter
def add_class(field, css_class):
    """
    Template filter to add a CSS class to a form field

    Usage:
        {{ form.field|add_class:"form-control" }}
    """
    return field.as_widget(attrs={"class": css_class})


@register.filter
def div(value, arg):
    """
    Divides the value by the argument

    Usage:
        {{ value|div:arg }}
    """
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def mul(value, arg):
    """
    Multiplies the value by the argument

    Usage:
        {{ value|mul:arg }}
    """
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0


@register.filter
def regroup_by(queryset, key_value):
    """
    Filter a queryset to only include items with a specific value

    Usage:
        {{ tasks|regroup_by:"completed" }}
    """
    result = []
    for item in queryset:
        if hasattr(item, "status") and item.status == key_value:
            result.append(item)
    return result


@register.filter
def count_by_status(queryset, status_value):
    """
    Count items in a queryset with a specific status

    Usage:
        {{ tasks|count_by_status:"completed" }}
    """
    count = 0
    for item in queryset:
        if hasattr(item, "status") and item.status == status_value:
            count += 1
    return count


@register.filter
def count_done(queryset):
    """
    Count items in a queryset that are marked as done

    Usage:
        {{ tasks|count_done }}
    """
    count = 0
    for item in queryset:
        if hasattr(item, "is_done") and item.is_done:
            count += 1
    return count


@register.filter
def multiply(value, arg):
    """
    Multiplies the value by the argument, similar to mul but works with template variable chains

    Usage:
        {{ value|multiply:100 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def subtract(value, arg):
    """
    Subtracts the argument from the value

    Usage:
        {{ value|subtract:arg }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0
