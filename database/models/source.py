from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from titlecase import titlecase


class Author(models.Model):
    """
    An author of a Source, i.e. a person who published it.
    """

    firstname = models.CharField(max_length=80)
    lastname = models.CharField(max_length=80)
    # Canonical cross-app identity (ORCID/affiliation live on provenance.Person).
    person = models.ForeignKey(
        "provenance.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="author_records",
    )

    class Meta:
        unique_together = ['firstname', 'lastname']
        ordering = ['lastname', 'firstname']

    @property
    def name(self):
        return f"{self.lastname}, {self.firstname}"

    def __str__(self):
        return self.name


class Source(models.Model):
    doi = models.CharField("DOI", blank=True, max_length=80)
    prime_id = models.CharField("Prime ID", blank=True, max_length=9)
    publication_year = models.CharField("Year of Publication", blank=True, max_length=4)
    source_title = models.CharField("Article Title", blank=True, max_length=300)
    journal_name = models.CharField("Journal Name", blank=True, max_length=300)
    journal_volume_number = models.CharField("Journal Volume Number", blank=True, max_length=10)
    page_numbers = models.CharField(
        "Page Numbers", blank=True, help_text="[page #]-[page #]", max_length=100
    )
    authors = models.ManyToManyField(Author, blank=True, through="Authorship")
    # FAIR metadata.
    url = models.URLField(blank=True)
    license = models.ForeignKey(
        "provenance.License",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sources",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    external_identifiers = GenericRelation("provenance.ExternalIdentifier")

    @property
    def pub_info(self):
        return (
            f"{self.journal_name}, "
            f"vol. {self.journal_volume_number}, "
            f"pp. {self.page_numbers}, "
            f"{self.publication_year}"
        )

    @property
    def author_line(self):
        return "; ".join(str(a.author) for a in self.authorship_set.order_by("order"))

    def __str__(self):
        authors = ", ".join(
            str(authorship.author) for authorship in self.authorship_set.order_by("order")
        )
        return f"""
        {titlecase(self.source_title)}:
        Published in {self.publication_year}:
            {self.journal_name},
            Vol. {self.journal_volume_number}
            Pgs. {self.page_numbers}
        Authors: {authors}
        """

    class Meta:
        ordering = ("prime_id",)


class Authorship(models.Model):
    """
    Who authored what paper.

    This allows many-to-many join between Sources (publications)
    and Authors, keeping track of author ordering on each publication.
    """

    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    order = models.IntegerField("Order of authorship")

    class Meta:
        ordering = ("order",)

    def __str__(self):
        return (
            f"{self.id} "
            f"Author: {self.author}, "
            f"Source: {self.source.source_title}, "
            f"Order: {self.order}"
        )
