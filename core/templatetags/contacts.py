"""Filters that turn the raw vendor contact columns into links.

The columns still hold whatever Access held (cleaned by ``core.contacts``),
templates need them split and shaped:

    {{ vendor.email1|emails }}       -> ["a@x.com", "b@y.com"]  (for mailto:)
    {{ vendor.website|website_url }} -> "https://x.com" or ""   (for href)
"""

from django import template

from core.contacts import clean_website, parse_emails

register = template.Library()


@register.filter
def emails(value):
    """``'a@x.com; b@y.com'`` -> ``['a@x.com', 'b@y.com']`` (real ones only)."""
    return parse_emails(value)


@register.filter
def website_url(value):
    """A full http(s) URL out of the Website column, or ``''`` if it holds none."""
    return clean_website(value)
