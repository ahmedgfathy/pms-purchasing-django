"""Normalize the vendor e-mail / website columns already in the database.

The Access back end stores those boxes as hyperlinks
(``a@b.com#mailto:a@b.com#``), so a plain load leaves the junk on screen.
``import_vendor_data`` cleans while it loads; this command applies the very
same ``core.contacts`` rules to rows that are already there, and is safe to
run as often as you like:

    manage.py normalize_vendor_contacts
"""

from collections import Counter

from django.core.management.base import BaseCommand

from core.contacts import CONTACT_FIELDS, clean_contacts
from core.models import Vendor


class Command(BaseCommand):
    help = "Clean the Access hyperlink junk out of the vendor contact columns."

    def handle(self, *args, **options):
        scanned = updated = 0
        per_field = Counter()
        dirty = []

        for vendor in Vendor.objects.all().iterator():
            scanned += 1
            before = {name: getattr(vendor, name) or "" for name in CONTACT_FIELDS}
            after = clean_contacts(dict(before))
            touched = [name for name in CONTACT_FIELDS if after[name] != before[name]]
            if not touched:
                continue
            updated += 1
            per_field.update(touched)
            for name in CONTACT_FIELDS:
                setattr(vendor, name, after[name])
            dirty.append(vendor)
            if len(dirty) >= 500:
                Vendor.objects.bulk_update(dirty, CONTACT_FIELDS)
                dirty = []
        if dirty:
            Vendor.objects.bulk_update(dirty, CONTACT_FIELDS)

        self.stdout.write("vendors scanned: %d" % scanned)
        if not updated:
            self.stdout.write(self.style.SUCCESS("all contact columns already clean"))
            return
        self.stdout.write(self.style.WARNING("vendors updated: %d" % updated))
        for name in CONTACT_FIELDS:
            if per_field[name]:
                self.stdout.write("  %-14s %6d changed" % (name, per_field[name]))
