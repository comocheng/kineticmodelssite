from django.core.management.base import BaseCommand
from django.db import transaction

from chemked_database.models import Apparatus, FileAuthor, ReferenceAuthor
from database.models import Author
from provenance.models import Institution, Person, SemanticMapping


def split_name(raw):
    """Best-effort split of a free-text author name into (given, family, full).

    Source author rows are dominantly ``First Last``. Some rows, however, cram an
    entire comma-separated author *list* (e.g. ``"A. Bee, C. Dee, ..."``) or a
    name + affiliation into a single row. Those contain two or more commas and
    cannot be split into one person, so they are kept verbatim as ``full_name``
    rather than mis-parsed as ``Last, First`` (which previously overflowed the
    given-name column).
    """
    raw = (raw or "").strip()
    if not raw:
        return "", "", ""
    if raw.count(",") >= 2:  # author list or name+affiliation -> keep verbatim
        return "", "", raw
    if "," in raw:  # "Last, First"
        family, _, given = raw.partition(",")
        return given.strip(), family.strip(), ""
    parts = raw.split()
    if len(parts) == 1:
        return "", "", raw  # single token -> keep as full_name
    return " ".join(parts[:-1]), parts[-1], ""  # "First M Last"


def ror_for_institution(name):
    """Look up a ROR id for an institution name via curated SSSOM rows."""
    m = (
        SemanticMapping.objects.filter(
            subject_label__iexact=name, object_id__istartswith="ror:"
        ).first()
    )
    return m.object_id.split(":", 1)[1] if m else ""


def get_or_create_person(name="", orcid="", given="", family="", full=""):
    """Resolve a canonical Person, preferring ORCID, then normalized name."""
    orcid = (orcid or "").strip()
    if not (given or family or full):
        given, family, full = split_name(name)
    if orcid:
        person, _ = Person.objects.get_or_create(
            orcid=orcid,
            defaults={"given_name": given, "family_name": family, "full_name": full},
        )
        if not (person.given_name or person.family_name or person.full_name):
            person.given_name, person.family_name, person.full_name = given, family, full
            person.save(update_fields=["given_name", "family_name", "full_name"])
        return person
    person, _ = Person.objects.get_or_create(
        orcid="", given_name=given, family_name=family, full_name=full
    )
    return person


class Command(BaseCommand):
    help = "Backfill provenance.Institution and provenance.Person from existing records."

    @transaction.atomic
    def handle(self, *args, **options):
        inst_count = 0
        for name in (
            Apparatus.objects.exclude(institution="")
            .values_list("institution", flat=True)
            .distinct()
        ):
            inst, made = Institution.objects.get_or_create(
                name=name.strip(),
                parent=None,
                defaults={"ror_id": ror_for_institution(name.strip())},
            )
            inst_count += int(made)
            Apparatus.objects.filter(
                institution=name, institution_ref__isnull=True
            ).update(institution_ref=inst)

        person_count = 0
        for author in Author.objects.filter(person__isnull=True):
            author.person = get_or_create_person(
                given=author.firstname, family=author.lastname
            )
            author.save(update_fields=["person"])
            person_count += 1

        for model in (FileAuthor, ReferenceAuthor):
            for a in model.objects.filter(person__isnull=True):
                a.person = get_or_create_person(name=a.name, orcid=a.orcid)
                a.save(update_fields=["person"])
                person_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Linked {inst_count} new institutions and {person_count} author rows to persons."
            )
        )
