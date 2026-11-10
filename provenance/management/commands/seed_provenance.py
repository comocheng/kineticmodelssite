from django.core.management.base import BaseCommand

from provenance.models import License


SEED_LICENSES = [
    ("MIT", "MIT License", "https://spdx.org/licenses/MIT"),
    ("BSD-3-Clause", "BSD 3-Clause", "https://spdx.org/licenses/BSD-3-Clause"),
    ("CC-BY-4.0", "Creative Commons Attribution 4.0", "https://creativecommons.org/licenses/by/4.0/"),
]


class Command(BaseCommand):
    help = "Seed baseline License rows used across the platform."

    def handle(self, *args, **options):
        for spdx, name, url in SEED_LICENSES:
            License.objects.get_or_create(spdx_id=spdx, defaults={"name": name, "url": url})
        self.stdout.write(self.style.SUCCESS("Seeded licenses."))
