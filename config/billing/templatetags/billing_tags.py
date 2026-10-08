from decimal import Decimal
from django import template

register = template.Library()

@register.filter(name="inr")
def inr_format(value):
    """
    Format a Decimal or numeric value in Indian Rupee format.
    Example: 1062.00 -> ₹1,062.00, 12500 -> ₹12,500.00
    """
    if value is None or value == "":
        return "₹0.00"
    try:
        val = Decimal(str(value))
        is_negative = val < 0
        val = abs(val)
        s, dec = f"{val:.2f}".split(".")
        if len(s) > 3:
            last_three = s[-3:]
            other = s[:-3]
            res = ""
            while len(other) > 2:
                res = "," + other[-2:] + res
                other = other[:-2]
            s = other + res + "," + last_three
        formatted = f"₹{s}.{dec}"
        return f"-{formatted}" if is_negative else formatted
    except Exception:
        return f"₹{value}"


@register.filter(name="multiply")
def multiply(value, arg):
    """
    Multiply two numbers in Django template.
    """
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except Exception:
        return Decimal("0.00")


@register.filter(name="subtract")
def subtract(value, arg):
    """
    Subtract arg from value in Django template.
    """
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except Exception:
        return Decimal("0.00")
