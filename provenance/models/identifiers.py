from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class IdentifierScheme(models.TextChoices):
    INCHIKEY = "inchikey", "InChIKey"
    INCHI = "inchi", "InChI"
    SMILES = "smiles", "SMILES"
    CAS = "cas", "CAS Registry Number"
    PUBCHEM = "pubchem.compound", "PubChem CID"
    CHEBI = "CHEBI", "ChEBI"
    CHEMBL = "chembl", "ChEMBL"
    DOI = "doi", "DOI"
    ORCID = "orcid", "ORCID"
    ROR = "ror", "ROR"
    PRIME = "prime", "PrIMe ID"


# Base URIs mirror mappings/prometheus.sssom.tsv curie_map.
_SCHEME_BASE = {
    IdentifierScheme.INCHIKEY: "https://www.inchi-trust.org/inchikey/",
    IdentifierScheme.PUBCHEM: "https://pubchem.ncbi.nlm.nih.gov/compound/",
    IdentifierScheme.CHEBI: "http://purl.obolibrary.org/obo/CHEBI_",
    IdentifierScheme.CHEMBL: "https://www.ebi.ac.uk/chembl/compound_report_card/",
    IdentifierScheme.DOI: "https://doi.org/",
    IdentifierScheme.ORCID: "https://orcid.org/",
    IdentifierScheme.ROR: "https://ror.org/",
}


class ExternalIdentifier(models.Model):
    """A persistent external identifier attached to any platform record.

    A generic relation lets one table serve Species, Source, KineticModel,
    CompositionSpecies, etc. (FAIR F1/I3 qualified references) without N nullable
    FKs.
    """

    scheme = models.CharField(max_length=40, choices=IdentifierScheme.choices, db_index=True)
    value = models.CharField(max_length=500, db_index=True)
    url = models.URLField(blank=True)
    is_primary = models.BooleanField(default=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    class Meta:
        db_table = "provenance_external_identifier"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["scheme", "value"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "scheme", "value"],
                name="provenance_unique_external_identifier",
            ),
        ]

    def __str__(self):
        return f"{self.scheme}:{self.value}"

    @property
    def uri(self) -> str:
        if self.url:
            return self.url
        base = _SCHEME_BASE.get(self.scheme)
        return f"{base}{self.value}" if base else self.value
