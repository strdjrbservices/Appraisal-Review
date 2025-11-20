from django import template

register = template.Library()

@register.filter(name='replace')
def replace(value, arg):
    """Replaces all occurrences of arg in the string with the second arg."""
    args = arg.split(',')
    return value.replace(args[0], args[1])