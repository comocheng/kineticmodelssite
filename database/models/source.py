from django.db import models


class Author(models.Model):
    """
    An author of a Source, i.e. a person who published it.
    """

    firstname = models.CharField(default="", max_length=80)
    lastname = models.CharField(default="", max_length=80)

    name = f"{lastname}, {firstname}"

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

    name = models.CharField("Model Name in Importer", blank=True, max_length=100)
    prime_id = models.CharField("Prime ID", blank=True, max_length=9, default="")
    publication_year = models.CharField("Year of Publication", blank=True, default="", max_length=4)
    source_title = models.CharField("Article Title", default="", blank=True, max_length=300)
    journal_name = models.CharField("Journal Name", blank=True, max_length=300)
    journal_volume_number = models.CharField("Journal Volume Number", blank=True, max_length=10)
    page_numbers = models.CharField(
        "Page Numbers", blank=True, help_text="[page #]-[page #]", max_length=100
    )
    authors = models.ManyToManyField(Author, blank=True, through="Authorship")
    doi = models.CharField(blank=True, max_length=80)  # not in PrIMe

    def __str__(self):
        self_string = ""
        self_string += "{s.source_title}:\n".format(s=self).upper()
        self_string += "Published in {s.publication_year}:\n".format(s=self)
        self_string += (
            "\t {s.journal_name},\n\t "
            "Vol. {s.journal_volume_number}\n\t "
            "Pgs. {s.page_numbers}\n".format(s=self)
        )
        self_string += "Authors: {s.authors}".format(s=self)

        return self_string

    class Meta:
        ordering = ("prime_id",)
        unique_together = ["publication_year", "source_title"]


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
