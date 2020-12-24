from django.db import models

from . import Species


class RevisionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(revision=True)


class SpeciesRevision(Species):
    objects = RevisionManager()

    class Meta:
        proxy = True
