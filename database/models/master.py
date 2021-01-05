from django.db import models


class MasterQuerySet(models.QuerySet):
    def latest(self):
        latest_pks = self.values_list("latest", flat=True)

        return self.model._meta.get_field("latest").remote_field.model.objects.filter(
            pk__in=latest_pks
        )


class MasterManager(models.Manager):
    def get_queryset(self):
        return MasterQuerySet(self.model, using=self._db)

    def latest(self):
        return self.get_queryset().latest()

    def create(*args, latest=None, original_id=None, **kwargs):
        if original_id is None and latest is not None:
            original_id = latest.original_id

        return super().create(*args, latest=latest, original_id=original_id, **kwargs)


class MasterMixin(models.Model):
    original_id = models.UUIDField(unique=True)

    objects = MasterManager()

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.latest)


class SpeciesMaster(MasterMixin):
    latest = models.OneToOneField("Species", related_name="master", on_delete=models.CASCADE)


class ReactionMaster(MasterMixin):
    latest = models.OneToOneField("Reaction", related_name="master", on_delete=models.CASCADE)


class KineticModelMaster(MasterMixin):
    latest = models.OneToOneField("KineticModel", related_name="master", on_delete=models.CASCADE)
