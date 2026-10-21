"""Link SemanticMapping rows to canonical platform records.

Each curated SSSOM row maps one subject entity to an external authority. This
command resolves the subject to the matching local record and sets the
appropriate foreign key so the mappings are queryable per entity:

  * chemical rows (``prom:`` subject) -> ``database.Species`` via the InChI in
    ``subject_match_field`` (RDKit InChIKey fallback against the InChIKey
    ``ExternalIdentifier`` rows).
  * reference rows (``promref:`` subject, ``doi:`` object) -> the curated
    ``chemked_database.ExperimentDataset`` (matched on the reference/file DOI)
    and/or the kinetic-model ``database.Source`` carrying that DOI.
  * organization rows (``promorg:`` subject, ``ror:`` object) ->
    ``provenance.Institution`` via ROR id, then name.
  * agent rows (``promagent:`` subject, ``orcid:`` object) ->
    ``provenance.Person`` via ORCID.
  * kinetic-model rows (``promkm:`` subject) -> ``database.KineticModel`` via
    Zenodo DOI, PrIMe id, or repository URL.

Idempotent: only rows whose resolved target changes are saved.
"""

import re

from django.core.management.base import BaseCommand

from chemked_database.models import ExperimentDataset
from database.models import KineticModel, Source, Species
from provenance.models import (
    ExternalIdentifier,
    IdentifierScheme,
    Institution,
    Person,
    SemanticMapping,
)

try:
    from rdkit import Chem
    from rdkit import RDLogger

    RDLogger.DisableLog("rdApp.*")
except ImportError:  # pragma: no cover
    Chem = None


def _strip(curie, prefix):
    """Return the local part of a CURIE (``doi:10.x`` -> ``10.x``)."""
    curie = (curie or "").strip()
    return curie[len(prefix):] if curie.startswith(prefix) else curie


class Command(BaseCommand):
    help = "Resolve SemanticMapping subjects to Species/Source/Institution/Person (idempotent)."

    def handle(self, *args, **options):
        species_linked, species_unresolved = self._link_species()
        ref_linked, ref_unresolved = self._link_references()
        model_linked, model_unresolved = self._link_kinetic_models()
        inst_linked, inst_unresolved = self._link_institutions()
        person_linked, person_unresolved = self._link_persons()
        app_linked, app_unresolved = self._link_apparatus()
        rxn_linked, rxn_unresolved = self._link_reactions()

        self.stdout.write(
            self.style.SUCCESS(
                "Linked mappings -> "
                f"species: {species_linked} ({species_unresolved} unresolved), "
                f"references: {ref_linked} ({ref_unresolved}), "
                f"kinetic-models: {model_linked} ({model_unresolved}), "
                f"institutions: {inst_linked} ({inst_unresolved}), "
                f"persons: {person_linked} ({person_unresolved}), "
                f"apparatus: {app_linked} ({app_unresolved}), "
                f"reactions: {rxn_linked} ({rxn_unresolved})."
            )
        )

    # -- species (chemical InChI rows) --------------------------------------
    def _link_species(self):
        inchi_map = {}
        for sp in Species.objects.prefetch_related("isomers").all():
            for iso in sp.isomers.all():
                if iso.inchi:
                    inchi_map.setdefault(iso.inchi, sp.pk)
        inchikey_map = dict(
            ExternalIdentifier.objects.filter(
                scheme=IdentifierScheme.INCHIKEY, content_type__model="species"
            ).values_list("value", "object_id")
        )

        linked = unresolved = 0
        for m in SemanticMapping.objects.filter(subject_match_field__startswith="InChI"):
            species_id = inchi_map.get(m.subject_match_field)
            if species_id is None and Chem is not None:
                key = Chem.InchiToInchiKey(m.subject_match_field)
                if key:
                    species_id = inchikey_map.get(key)
            if species_id is None:
                unresolved += 1
                continue
            if m.species_id != species_id:
                m.species_id = species_id
                m.save(update_fields=["species"])
                linked += 1
        return linked, unresolved

    # -- references (DOI rows -> ExperimentDataset and/or Source) ------------
    def _link_references(self):
        source_map = {
            (doi or "").strip().lower(): pk
            for pk, doi in Source.objects.exclude(doi="").values_list("id", "doi")
        }
        dataset_map = {}
        for pk, ref_doi, file_doi in ExperimentDataset.objects.values_list(
            "id", "reference_doi", "file_doi"
        ):
            for doi in (ref_doi, file_doi):
                doi = (doi or "").strip().lower()
                if doi:
                    dataset_map.setdefault(doi, pk)

        linked = unresolved = 0
        for m in SemanticMapping.objects.filter(
            object_id__startswith="doi:"
        ).exclude(subject_id__startswith="promkm:"):
            doi = _strip(m.object_id, "doi:").lower()
            source_id = source_map.get(doi)
            dataset_id = dataset_map.get(doi)
            if source_id is None and dataset_id is None:
                unresolved += 1
                continue
            changed = []
            if source_id is not None and m.source_id != source_id:
                m.source_id = source_id
                changed.append("source")
            if dataset_id is not None and m.experiment_dataset_id != dataset_id:
                m.experiment_dataset_id = dataset_id
                changed.append("experiment_dataset")
            if changed:
                m.save(update_fields=changed)
                linked += 1
        return linked, unresolved

    # -- kinetic models (promkm DOI / PrIMe / repository rows) ---------------
    def _link_kinetic_models(self):
        def _norm_doi(value):
            value = (value or "").strip().lower()
            return re.sub(r"^https?://(dx\.)?doi\.org/", "", value)

        by_doi = {}
        by_prime = {}
        by_repo = {}
        for pk, zen, prime, repo in KineticModel.objects.values_list(
            "id", "zenodo_doi", "prime_id", "repository_url"
        ):
            doi = _norm_doi(zen)
            if doi:
                by_doi.setdefault(doi, pk)
            pid = (prime or "").strip().lower()
            if pid:
                by_prime.setdefault(pid, pk)
            url = (repo or "").strip().lower().rstrip("/")
            if url:
                by_repo.setdefault(url, pk)

        linked = unresolved = 0
        for m in SemanticMapping.objects.filter(subject_id__startswith="promkm:"):
            obj = m.object_id
            if obj.startswith("doi:"):
                km_id = by_doi.get(_norm_doi(_strip(obj, "doi:")))
            elif obj.startswith("prime:"):
                km_id = by_prime.get(_strip(obj, "prime:").lower())
            else:
                km_id = by_repo.get(obj.strip().lower().rstrip("/"))
            if km_id is None:
                unresolved += 1
                continue
            if m.kinetic_model_id != km_id:
                m.kinetic_model_id = km_id
                m.save(update_fields=["kinetic_model"])
                linked += 1
        return linked, unresolved

    # -- institutions (organization ROR rows) -------------------------------
    def _link_institutions(self):
        by_ror = {
            (ror or "").strip().lower(): pk
            for pk, ror in Institution.objects.exclude(ror_id="").values_list("id", "ror_id")
        }
        by_name = {
            (name or "").strip().lower(): pk
            for pk, name in Institution.objects.values_list("id", "name")
        }
        linked = unresolved = 0
        for m in SemanticMapping.objects.filter(object_id__startswith="ror:"):
            ror = _strip(m.object_id, "ror:").lower()
            inst_id = by_ror.get(ror) or by_name.get((m.subject_label or "").strip().lower())
            if inst_id is None:
                unresolved += 1
                continue
            if m.institution_id != inst_id:
                m.institution_id = inst_id
                m.save(update_fields=["institution"])
                linked += 1
        return linked, unresolved

    # -- persons (agent ORCID rows) -----------------------------------------
    def _link_persons(self):
        by_orcid = {
            (orcid or "").strip().lower(): pk
            for pk, orcid in Person.objects.exclude(orcid="").values_list("id", "orcid")
        }
        linked = unresolved = 0
        for m in SemanticMapping.objects.filter(object_id__startswith="orcid:"):
            orcid = _strip(m.object_id, "orcid:").lower()
            person_id = by_orcid.get(orcid)
            if person_id is None:
                unresolved += 1
                continue
            if m.person_id != person_id:
                m.person_id = person_id
                m.save(update_fields=["person"])
                linked += 1
        return linked, unresolved

    # -- apparatus (promapp instance rows) ----------------------------------
    def _link_apparatus(self):
        from chemked_database.models import Apparatus

        slug_map = {}
        for ap in Apparatus.objects.select_related("institution_ref").all():
            slug = ap.sssom_slug
            if slug:
                slug_map.setdefault(slug, ap.pk)

        linked = unresolved = 0
        for m in SemanticMapping.objects.filter(subject_id__startswith="promapp:"):
            ap_id = slug_map.get(_strip(m.subject_id, "promapp:"))
            if ap_id is None:
                unresolved += 1
                continue
            if m.apparatus_id != ap_id:
                m.apparatus_id = ap_id
                m.save(update_fields=["apparatus"])
                linked += 1
        return linked, unresolved

    # -- reactions (promrxn instance rows) ----------------------------------
    def _link_reactions(self):
        from database.models import Reaction

        hash_map = dict(
            Reaction.objects.exclude(hash="").values_list("hash", "id")
        )
        linked = unresolved = 0
        for m in SemanticMapping.objects.filter(subject_id__startswith="promrxn:"):
            rxn_id = hash_map.get(_strip(m.subject_id, "promrxn:"))
            if rxn_id is None:
                unresolved += 1
                continue
            if m.reaction_id != rxn_id:
                m.reaction_id = rxn_id
                m.save(update_fields=["reaction"])
                linked += 1
        return linked, unresolved
