from django.db import models


class Author(models.Model):
    """
    An author of a Source, i.e. a person who published it.
    """
    name = models.CharField(help_text='format: surname, firstname',
                            max_length=80)

    def __unicode__(self):
        return unicode(self.name)


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
    bPrimeID = models.CharField('Prime ID',
                                blank=True,
                                max_length=9,
                                default='')
    publicationYear = models.CharField('Year of Publication',
                                       blank=True,
                                       default='',
                                       max_length=4)
    sourceTitle = models.CharField(default='', blank=True, max_length=300)
    journalName = models.CharField(blank=True, max_length=300)
    journalVolumeNumber = models.CharField('Journal Volume Number',
                                           blank=True,
                                           max_length=10)
    pageNumbers = models.CharField(blank=True,
                                   help_text='[page #]-[page #]',
                                   max_length=100)
    authors = models.ManyToManyField(Author, blank=True, through='Authorship')
    doi = models.CharField(blank=True, max_length=80)  # not in PrIMe

    def __unicode__(self):
        self_string = u""
        self_string += u"{s.sourceTitle}:\n".format(s=self).upper()
        self_string += u"Published in {s.publicationYear}:\n".format(s=self)
        self_string += u"\t {s.journalName},\n\t " \
                       u"Vol. {s.journalVolumeNumber}\n\t " \
                       u"Pgs. {s.pageNumbers}\n".format(s=self)
        # self_string += u"Authors: {s.authors}".format(s=self)

        return self_string

    class Meta:
        ordering = ('bPrimeID',)
        # unique_together = ["pub_year", "pub_name"]


class Authorship(models.Model):
    """
    Who authored what paper.

    This allows many-to-many join between Sources (publications)
    and Authors, keeping track of author ordering on each publication.
    """
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    order = models.IntegerField('Order of authorship')

    def __unicode__(self):
        return (u"{s.id} author {s.author} "
                "was # {s.order} in {s.source}").format(s=self)
