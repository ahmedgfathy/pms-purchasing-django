"""Cleaning for the vendor contact columns (e-mail + website).

The Access back end stored these columns as *hyperlinks*, so mdbtools hands
us Jet's ``display#target#`` encoding — ``a@b.com#mailto:a@b.com#`` or
``www.site.com#http://www.site.com#`` — mixed with pasted junk (company
names, Outlook file paths, an address typed into the wrong column).

Everything here is idempotent: normalizing already-normalized data returns
it unchanged, so the import, the vendor form and the
``normalize_vendor_contacts`` command can all call the same functions.
"""

from __future__ import annotations

import re

# The six e-mail boxes of a vendor, in the order they are stored.  Together
# with "website" they are the only columns this module touches.
EMAIL_FIELDS = (
    "email1", "email2", "email3",
    "agent_email1", "agent_email2", "agent_email3",
)
CONTACT_FIELDS = EMAIL_FIELDS + ("website",)

# Strict enough to stop "a@b" and junk like "x@y,com" before repair, loose
# enough for ".eg", ".info" and the ".co.uk" style double endings.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s#\"'<>]+", re.IGNORECASE)
# Host labels of letters/digits/hyphens with a *lower-case* final label —
# that keeps "A. Albert GmbH" and "DOF Egypt" out of the Website column
# while www.PETROLVALVES.it and www.3e.com.eg pass.
HOST_RE = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[a-z]{2,}$")


def _repair(text):
    """Undo the spacing typos people type into an address box."""
    text = re.sub(r"[ \t]*@[ \t]*", "@", text)                              # info @x.com
    text = re.sub(r"([A-Za-z0-9])[ \t]+\.(?=[A-Za-z]{2,})", r"\1.", text)   # x@site .com
    text = re.sub(                                                           # x@site -group.com
        r"@([A-Za-z0-9.\-]+)[ \t]+([A-Za-z0-9.\-]*\.[A-Za-z]{2,})", r"@\1\2", text,
    )
    return re.sub(r"@([A-Za-z0-9\-]+),([A-Za-z]{2,})\b", r"@\1.\2", text)   # x@site,com


def parse_emails(raw):
    """Every deliverable address in ``raw``, in order, without repeats."""
    if not raw:
        return []
    seen, found = set(), []
    for address in EMAIL_RE.findall(_repair(str(raw))):
        key = address.lower()
        if key not in seen:
            seen.add(key)
            found.append(address)
    return found


def clean_emails(raw):
    """``raw`` reduced to a ``'; '-separated list of real addresses."""
    return "; ".join(parse_emails(raw))


def _url_from(part):
    """One ``#``-separated fragment -> a full URL, or None if it is not one."""
    part = re.sub(r"\s+", "", part)  # Access wraps long targets over lines
    if not part or "@" in part or "\\" in part:
        return None
    if URL_RE.match(part):
        host = part.split("://", 1)[1].split("/", 1)[0].split("?", 1)[0]
        return part if HOST_RE.match(host) else None
    host = part.split("/", 1)[0].split("?", 1)[0]
    return "https://" + part if HOST_RE.match(host) else None


def clean_website(raw):
    """First real web address in ``raw`` (Access ``display#target#``), with
    a scheme — or ``''`` when the column holds no site at all."""
    if not raw:
        return ""
    parts = str(raw).split("#")
    # the address Access would open first, then the readable text
    for with_scheme in (True, False):
        for part in parts:
            if with_scheme != bool(URL_RE.match(re.sub(r"\s+", "", part))):
                continue
            url = _url_from(part)
            if url:
                return url
    return ""


def clean_contacts(data):
    """Normalize the contact columns of one vendor (mutates ``data``).

    Beyond tidying every box this fixes the columns Access mixed up: a URL
    typed into a mail box fills an empty Website, an address typed into the
    Website box fills an empty E-mail 1, and addresses pasted into several
    boxes are kept only in the first one.
    """
    raw = {name: data.get(name) or "" for name in CONTACT_FIELDS}

    website = clean_website(raw["website"])
    if not website:
        for name in EMAIL_FIELDS:
            website = clean_website(raw[name])
            if website:
                break
    data["website"] = website

    addresses = {name: parse_emails(raw[name]) for name in EMAIL_FIELDS}
    if not addresses["email1"]:
        addresses["email1"] = parse_emails(raw["website"])

    for group in (
        ("email1", "email2", "email3"),
        ("agent_email1", "agent_email2", "agent_email3"),
    ):
        seen = set()
        for name in group:
            kept = []
            for address in addresses[name]:
                key = address.lower()
                if key not in seen:
                    seen.add(key)
                    kept.append(address)
            addresses[name] = kept

    for name in EMAIL_FIELDS:
        data[name] = "; ".join(addresses[name])
    return data
