from django.db import models


class License(models.Model):
    """A reuse license (prom:License), identified by SPDX id."""

    spdx_id = models.CharField(
        "SPDX ID",
        max_length=100,
        unique=True,
        help_text="SPDX identifier, e.g. MIT, BSD-3-Clause, CC-BY-4.0",
    )
    name = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)

    class Meta:
        db_table = "provenance_license"
        ordering = ["spdx_id"]

    def __str__(self):
        return self.spdx_id

    @property
    def uri(self) -> str:
        return self.url or f"https://spdx.org/licenses/{self.spdx_id}"
