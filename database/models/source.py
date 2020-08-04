from django.db import models


class Author(models.Model):
    """
    An author of a Source, i.e. a person who published it.
    """

    firstname = models.CharField(max_length=80)
    lastname = models.CharField(max_length=80)

    @property
    def name(self):
        return f"{self.lastname}, {self.firstname}"

    def __str__(self):
        return self.name


class Source(models.Model):
    """
    A source, or bibliography item.

    This is equivalent of a 'Bibliography' entry in PrIMe, which contain:
    *****in catalog******
    publication year
    authors
    source title
    journal name
    journal volume
    page numbers
    """

    doi = models.CharField(blank=True, max_length=80)
    prime_id = models.CharField("Prime ID", blank=True, max_length=9)
    publication_year = models.CharField("Year of Publication", blank=True, max_length=4)
    source_title = models.CharField("Article Title", blank=True, max_length=300)
    journal_name = models.CharField("Journal Name", blank=True, max_length=300)
    journal_volume_number = models.CharField("Journal Volume Number", blank=True, max_length=10)
    page_numbers = models.CharField(
        "Page Numbers", blank=True, help_text="[page #]-[page #]", max_length=100
    )
    authors = models.ManyToManyField(Author, blank=True, through="Authorship")

    def __str__(self):
        authors = ", ".join(
            str(authorship.author) for authorship in self.authorship_set.order_by("order")
        )
        return f"""
        {self.source_title.upper()}:
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

    def __str__(self):
        return ("{s.id} author {s.author} " "was # {s.order} in {s.source}").format(s=self)
