from django.db import models


class Institution(models.Model):
    """A research organization (prov:Agent / foaf:Organization), identified by ROR.

    Referenced by experimental apparatus and by person affiliations. A named lab
    can point to its parent university via ``parent``. Aligns with the ontology
    classes ``ontokin:Organization`` / ``prom:Authority``.
    """

    name = models.CharField(max_length=255)
    ror_id = models.CharField(
        "ROR ID",
        max_length=255,
        blank=True,
        db_index=True,
        help_text="ROR identifier or URL, e.g. https://ror.org/00f54p054",
    )
    country = models.CharField(max_length=100, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_units",
        help_text="Parent organization (e.g. the university for a named lab).",
    )

    class Meta:
        db_table = "provenance_institution"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"], name="provenance_unique_institution"
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def ror_uri(self) -> str:
        if not self.ror_id:
            return ""
        return self.ror_id if self.ror_id.startswith("http") else f"https://ror.org/{self.ror_id}"


class Person(models.Model):
    """A person (prov:Agent / schema:Person), identified by ORCID.

    Canonical identity that the per-context author rows link to
    (``database.Author``, ``chemked_database.FileAuthor`` / ``ReferenceAuthor``).
    """

    given_name = models.CharField(max_length=255, blank=True)
    family_name = models.CharField(max_length=255, blank=True)
    full_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name when given/family cannot be split.",
    )
    orcid = models.CharField(
        "ORCID",
        max_length=50,
        blank=True,
        db_index=True,
        help_text="ORCID iD, e.g. 0000-0002-1825-0097",
    )
    affiliation = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="people",
    )

    class Meta:
        db_table = "provenance_person"
        ordering = ["family_name", "given_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["orcid"],
                condition=models.Q(orcid__gt=""),
                name="provenance_unique_orcid",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def name(self) -> str:
        if self.family_name or self.given_name:
            return f"{self.family_name}, {self.given_name}".strip(", ")
        return self.full_name or f"Person {self.pk}"

    @property
    def orcid_uri(self) -> str:
        if not self.orcid:
            return ""
        return self.orcid if self.orcid.startswith("http") else f"https://orcid.org/{self.orcid}"
