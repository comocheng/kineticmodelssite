from django.db import models


class SemanticMapping(models.Model):
    """One SSSOM mapping row (FAIR I3 cross-reference).

    Mirrors ``mappings/prometheus.sssom.tsv`` so curated mappings are queryable
    through the API instead of only downloadable as TSV.
    """

    mapping_set_id = models.CharField(max_length=255, blank=True, db_index=True)
    subject_id = models.CharField(max_length=255, db_index=True)
    subject_label = models.CharField(max_length=255, blank=True)
    predicate_id = models.CharField(max_length=255, default="skos:exactMatch")
    object_id = models.CharField(max_length=255, db_index=True)
    object_label = models.CharField(max_length=255, blank=True)
    mapping_justification = models.CharField(max_length=255, blank=True)
    subject_match_field = models.CharField(max_length=255, blank=True)
    confidence = models.FloatField(default=1.0)
    mapping_tool = models.CharField(max_length=255, blank=True)
    mapping_date = models.DateField(null=True, blank=True)
    author_id = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)

    species = models.ForeignKey(
        "database.Species",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )
    source = models.ForeignKey(
        "database.Source",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )
    experiment_dataset = models.ForeignKey(
        "chemked_database.ExperimentDataset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )
    kinetic_model = models.ForeignKey(
        "database.KineticModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )
    institution = models.ForeignKey(
        "provenance.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )
    person = models.ForeignKey(
        "provenance.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )
    apparatus = models.ForeignKey(
        "chemked_database.Apparatus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )
    reaction = models.ForeignKey(
        "database.Reaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_mappings",
    )

    class Meta:
        db_table = "provenance_semantic_mapping"
        ordering = ["subject_id", "-confidence"]
        indexes = [
            models.Index(fields=["subject_id"]),
            models.Index(fields=["object_id"]),
            models.Index(fields=["predicate_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["subject_id", "predicate_id", "object_id"],
                name="provenance_unique_mapping",
            ),
        ]

    def __str__(self):
        return f"{self.subject_id} {self.predicate_id} {self.object_id}"
