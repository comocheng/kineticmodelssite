import logging
import math
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import habanero
from django.db import transaction, IntegrityError
from dateutil import parser
from rmgpy import kinetics, constants
from rmgpy.quantity import RateCoefficient
from database.scripts.rmg_libraries import TolerantKineticsLibrary
from rmgpy.data.thermo import ThermoLibrary
from rmgpy.thermo import NASA, ThermoData, Wilhoit, NASAPolynomial

from django.conf import settings
from database.models import kinetic_data as kd


"""
Import Flow:
* Kinetic Model: update CharFields
* Source: update CharFields & Authors
* Thermo (Entry): update thermo data (coeffs, reference state) & source
* Kinetics: update prime_id, source, uncertainty, data, & reaction prime_id
1. Kinetic Model
    * Get or Create Kinetic Model with RMG-model name
    * Update fields available in RMG-models
    * Import Sources
    * Import Thermo
    * Import Kinetics
2. Sources:
    * Get as many fields as possible
    * Get or create the Source
    * Try to save Source (errors: blank required fields -> response: skip)
    * Get author data
    * Get or create Authors
    * Create Authorships
    * Try to save Authorships (errors: no author data -> response: keep source but no authors)

3. Thermo:
    * Load thermo library (errors: fails -> response: skip)
    * Get the Species (errors: no species -> response: skip)
    * Get as many fields as possible
    * Try to save Thermo (errors: blank required fields -> response: skip)
    * Create the Species Isomers & Structures (errors: no/missing isomers/structures -> response: keep species & skip missing)
    * Link Species and save
"""  # noqa: E501

logger = logging.getLogger(__name__)

if getattr(settings, "SILENCE_RMG_IMPORT_LOGS", False):
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False
else:
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename="importer.log", mode="w")
    handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False


def safe_import(func, *args, error_message=None, **kwargs):
    try:
        with transaction.atomic():
            func(*args, **kwargs)
    except Exception:
        message = error_message or f"Failed to execute {func.__name__}"
        logger.exception(message)


def import_rmg_models(apps, schema_editor):
    model_names = [
        "KineticModel",
        "Source",
        "Author",
        "Authorship",
        "Thermo",
        "ThermoComment",
        "Species",
        "Formula",
        "Isomer",
        "Structure",
        "SpeciesName",
        "Efficiency",
        "Kinetics",
        "KineticsComment",
        "Reaction",
        "Stoichiometry",
    ]
    models = SimpleNamespace()
    logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    for name in model_names:
        setattr(models, name, apps.get_model("database", name))
    path = os.getenv("RMGMODELSPATH", "./rmg-models/")


    skip_list = ["PCI2011/193-Mehl"]
    model_paths = get_models(path, skip_list)

    for rmg_model_name, thermo_path, kinetics_path, source_path in model_paths:
        logger.info(f"IMPORTING KINETIC MODEL: {rmg_model_name}")
        safe_import(
            import_kinetic_model, rmg_model_name, thermo_path, kinetics_path, source_path, models
        )


def import_kinetic_model(rmg_model_name, thermo_path, kinetics_path, source_path, models):
    now = datetime.now()
    kinetic_model, created = models.KineticModel.objects.get_or_create(
        model_name=rmg_model_name,
        defaults={"info": f"Imported via RMG-models migration at {now.isoformat()}"},
    )
    if not created:
        # Keep the import idempotent: update the info timestamp but don't crash.
        kinetic_model.info = f"Re-imported via RMG-models migration at {now.isoformat()}"
        kinetic_model.save(update_fields=["info"])
    logger.info(f"Importing Source {source_path}")
    safe_import(import_source, source_path, kinetic_model, models)
    logger.info(f"Importing Thermo Library {thermo_path}")
    safe_import(import_thermo, thermo_path, kinetic_model, models)
    logger.info(f"Importing Kinetics Library {kinetics_path}")
    safe_import(import_kinetics, kinetics_path, kinetic_model, models)


def safe_save(instance):
    try:
        instance.save()
        return instance
    except Exception:
        logger.exception(f"Error when saving instance of {instance.__class__.__qualname__}")


def filter_fields(fields, filter_value=None):
    return {k: v for k, v in fields.items() if v != filter_value}


def get_species_hash(isomers):
    isomer_fingerprint = "".join(sorted(set(str(isomer.id) for isomer in isomers)))

    return hashlib.md5(bytes(isomer_fingerprint, "UTF-8")).hexdigest()


def get_or_create_species(kinetic_model, name, molecules, models):
    formula = molecules[0].get_formula()
    formula_obj, _ = models.Formula.objects.get_or_create(formula=formula)
    isomers = []
    for molecule in molecules:
        smiles = molecule.to_smiles()
        augmented_inchi = molecule.to_augmented_inchi()
        adjacency_list = molecule.to_adjacency_list()
        multiplicity = molecule.multiplicity
        isomer, _ = models.Isomer.objects.get_or_create(inchi=augmented_inchi, formula=formula_obj)
        isomers.append(isomer)

        # Deduplicate by molecular graph isomorphism, not just adjacency
        # list text.  Different atom numberings produce different text but
        # represent the same molecule.
        existing = models.Structure.objects.filter(
            isomer=isomer, multiplicity=multiplicity,
        )
        match = None
        for candidate in existing:
            try:
                if candidate.to_rmg().is_isomorphic(molecule):
                    match = candidate
                    break
            except Exception:
                continue
        if match is None:
            models.Structure.objects.get_or_create(
                adjacency_list=adjacency_list,
                defaults={"smiles": smiles, "multiplicity": multiplicity, "isomer": isomer},
            )

    species_hash = get_species_hash(isomers)
    species, species_created = models.Species.objects.get_or_create(hash=species_hash)
    if species_created:
        species.isomers.add(*isomers)

    models.SpeciesName.objects.get_or_create(
        name=name, species=species, kinetic_model=kinetic_model
    )

    return species


def get_reaction_hash(stoich_data):
    reaction_fingerprint = "".join(
        sorted(set(f"{stoich:.4f}{species.id}" for stoich, species in stoich_data))
    )

    return hashlib.md5(bytes(reaction_fingerprint, "UTF-8")).hexdigest()


def index_new_rows(models, reaction=None, kinetics=None):
    """Keep the shared chemical identity current for new rows. Skipped when an old data
    migration runs this importer with historical models, which lack these fields."""
    from database.models import Reaction
    if getattr(models, "Reaction", None) is not Reaction:
        return
    from database.services import chemistry_index
    if reaction is not None:
        chemistry_index.index_reaction(reaction)
    if kinetics is not None:
        kinetics.rate_fingerprint = chemistry_index.kinetics_fingerprint(kinetics)
        kinetics.save(update_fields=["rate_fingerprint"])


def get_or_create_reaction(kinetic_model, rmg_reaction, models):
    """
    Create and save a reaction from an RMG reaction

    The kinetic model argument is needed to create species that are not yet in the database.
    If a reaction already exists, it is looked up and returned.
    The uniqueness of a reaction consists of a set of species
    and respective stoichiometric coefficients.
    """

    reversible = rmg_reaction.reversible
    reactants = rmg_reaction.reactants
    products = rmg_reaction.products
    reaction_species = [*reactants, *products]
    stoich_data = []
    species_map = {}
    for s in reaction_species:
        name = s.label
        if species_map.get(name) is None:
            species_map[name] = s

    with transaction.atomic():
        for rmg_species in species_map.values():
            species = get_or_create_species(
                kinetic_model,
                "",
                rmg_species.molecule,
                models,
            )
            reactant_coeff = sum(-1 for reactant in reactants if reactant == rmg_species)
            product_coeff = sum(1 for product in products if product == rmg_species)

            if reactant_coeff != 0:
                stoich_data.append((reactant_coeff, species))
            if product_coeff != 0:
                stoich_data.append((product_coeff, species))

        reaction, created = models.Reaction.objects.get_or_create(
            hash=get_reaction_hash(stoich_data=stoich_data), defaults={"reversible": reversible}
        )
        if created:
            for stoich_coeff, species in stoich_data:
                models.Stoichiometry.objects.create(
                    reaction=reaction, species=species, coeff=stoich_coeff
                )
            index_new_rows(models, reaction=reaction)

        stoich_reactants = reaction.stoichiometry_set.filter(coeff__lte=0)
        stoich_products = reaction.stoichiometry_set.filter(coeff__gte=0)
        if not (stoich_reactants or stoich_products):
            reactants_or_products = "reactants" if not stoich_reactants else "products"
            raise IntegrityError(f"Reaction cannot have zero {reactants_or_products}")

    return reaction


def create_arrhenius(rmg_kinetics_data):
    return kd.Arrhenius(
        type="arrhenius",
        a=rmg_kinetics_data.A.value,
        a_si=rmg_kinetics_data.A.value_si,
        a_units=rmg_kinetics_data.A.units,
        n=rmg_kinetics_data.n.value_si,
        e=rmg_kinetics_data.Ea.value,
        e_si=rmg_kinetics_data.Ea.value_si,
        e_units=rmg_kinetics_data.Ea.units,
    )


def create_arrhenius_ep(rmg_kinetics_data):
    return kd.ArrheniusEP(
        type="arrhenius_ep",
        a=rmg_kinetics_data.A.value,
        a_si=rmg_kinetics_data.A.value_si,
        a_units=rmg_kinetics_data.A.units,
        n=rmg_kinetics_data.n.value_si,
        alpha=rmg_kinetics_data.alpha.value_si,
        e0=rmg_kinetics_data.E0.value,
        e0_si=rmg_kinetics_data.E0.value_si,
        e0_units=rmg_kinetics_data.E0.units,
    )


def create_multi_arrhenius(rmg_kinetics_data):
    return kd.MultiArrhenius(
        type="multi_arrhenius",
        arrhenius_set=[
            create_arrhenius(rmg_arrhenius) for rmg_arrhenius in rmg_kinetics_data.arrhenius
        ],
    )


def create_pdep_arrhenius(rmg_kinetics_data):
    return kd.PDepArrhenius(
        type="pdep_arrhenius",
        pressure_set=[
            kd.Pressure(arrhenius=create_multi_arrhenius(a) if isinstance(a, kinetics.MultiArrhenius)
                        else create_arrhenius(a), pressure=p)
            for p, a in zip(rmg_kinetics_data.pressures.value_si, rmg_kinetics_data.arrhenius)
        ],
    )


def create_multi_pdep_arrhenius(rmg_kinetics_data):
    return kd.MultiPDepArrhenius(
        type="multi_pdep_arrhenius",
        pdep_arrhenius_set=[create_pdep_arrhenius(a) for a in rmg_kinetics_data.arrhenius],
    )


def create_chebyshev(rmg_kinetics_data):
    # RMG adds log10 of the kunits-to-SI factor to coeffs[0, 0]; store them as written, in kunits.
    coeffs = rmg_kinetics_data.coeffs.value_si.copy()
    coeffs[0, 0] -= math.log10(RateCoefficient(1.0, rmg_kinetics_data.kunits).value_si)
    return kd.Chebyshev(
        type="chebyshev",
        coefficient_matrix=coeffs.tolist(),
        units=rmg_kinetics_data.kunits,
    )


def create_third_body(rmg_kinetics_data):
    return kd.ThirdBody(
        type="third_body",
        low_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusLow),
    )


def create_lindemann(rmg_kinetics_data):
    return kd.Lindemann(
        type="lindemann",
        low_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusLow),
        high_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusHigh),
    )


def create_troe(rmg_kinetics_data):
    troe_fields = filter_fields(
        {
            "t1": rmg_kinetics_data.T1.value_si if rmg_kinetics_data.T1 is not None else None,
            "t2": rmg_kinetics_data.T2.value_si if rmg_kinetics_data.T2 is not None else None,
            "t3": rmg_kinetics_data.T3.value_si if rmg_kinetics_data.T3 is not None else None,
        }
    )
    return kd.Troe(
        type="troe",
        low_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusLow),
        high_arrhenius=create_arrhenius(rmg_kinetics_data.arrheniusHigh),
        alpha=rmg_kinetics_data.alpha,
        **troe_fields,
    )


def create_general_kinetics_data(rmg_kinetics_data):
    return kd.KineticsData(
        type="kinetics_data",
        temps=rmg_kinetics_data.Tdata,
        rate_coeffs=rmg_kinetics_data.kdata,
    )


def create_and_save_efficiencies(kinetic_model, kinetics_instance, rmg_kinetics_data, models):
    for rmg_molecule, efficiency in rmg_kinetics_data.efficiencies.items():
        species = get_or_create_species(kinetic_model, "", [rmg_molecule], models)
        efficiency = models.Efficiency.objects.create(
            species=species, kinetics=kinetics_instance, efficiency=efficiency
        )
        efficiency.save()


def get_base_kinetics_data_fields(rmg_kinetics_data):
    return filter_fields(
        {
            "min_temp": rmg_kinetics_data.Tmin.value_si
            if rmg_kinetics_data.Tmin is not None
            else None,
            "max_temp": rmg_kinetics_data.Tmax.value_si
            if rmg_kinetics_data.Tmax is not None
            else None,
            "min_pressure": rmg_kinetics_data.Pmin.value_si
            if rmg_kinetics_data.Pmin is not None
            else None,
            "max_pressure": rmg_kinetics_data.Pmax.value_si
            if rmg_kinetics_data.Pmax is not None
            else None,
        }
    )


def create_kinetics_data(kinetic_model, rmg_kinetics_data, models):
    kinetics_factory = {
        "KineticsData": create_general_kinetics_data,
        "Arrhenius": create_arrhenius,
        "ArrheniusEP": create_arrhenius_ep,
        "MultiArrhenius": create_multi_arrhenius,
        "PDepArrhenius": create_pdep_arrhenius,
        "MultiPDepArrhenius": create_multi_pdep_arrhenius,
        "Chebyshev": create_chebyshev,
        "ThirdBody": create_third_body,
        "Lindemann": create_lindemann,
        "Troe": create_troe,
    }
    model_name = rmg_kinetics_data.__class__.__name__
    kinetics_data = kinetics_factory[model_name](rmg_kinetics_data).dict()

    return kinetics_data


def kinetics_local_context():
    """The names an RMG-format reactions.py may use for its kinetics."""
    return {
        "KineticsData": kinetics.KineticsData,
        "Arrhenius": kinetics.Arrhenius,
        "ArrheniusEP": kinetics.ArrheniusEP,
        "MultiArrhenius": kinetics.MultiArrhenius,
        "MultiPDepArrhenius": kinetics.MultiPDepArrhenius,
        "PDepArrhenius": kinetics.PDepArrhenius,
        "Chebyshev": kinetics.Chebyshev,
        "ThirdBody": kinetics.ThirdBody,
        "Lindemann": kinetics.Lindemann,
        "Troe": kinetics.Troe,
        "R": constants.R,
    }


def import_kinetics(kinetics_path, kinetic_model, models, only_types=None):
    """Import a model's kinetics library; only_types limits it to RMG kinetics class names.

    Returns counts of imported, skipped and failed entries."""
    local_context = kinetics_local_context()
    # Older RMG accepted reactions that RMG 4 refuses; skip just those, not the whole library.
    library = TolerantKineticsLibrary(label=kinetic_model.model_name)
    library.SKIP_DUPLICATES = True
    library.load(kinetics_path, local_context=local_context)
    counts = {"imported": 0, "skipped": 0, "failed": 0, "rejected": len(library.rejected)}
    for label, reason in library.rejected:
        logger.warning(f"RMG cannot load reaction {label} ({reason}); skipped")
    for entry in library.entries.values():
        if only_types is not None and entry.data.__class__.__name__ not in only_types:
            counts["skipped"] += 1
            continue
        try:
            with transaction.atomic():
                rmg_kinetics_data = entry.data
                comment = entry.short_desc
                rmg_reaction = entry.item
                reaction = get_or_create_reaction(kinetic_model, rmg_reaction, models)
                kinetics_data = create_kinetics_data(kinetic_model, rmg_kinetics_data, models)
                base_fields = get_base_kinetics_data_fields(rmg_kinetics_data)

                kinetics_instance, created = models.Kinetics.objects.get_or_create(
                    reaction=reaction, raw_data=kinetics_data, defaults=base_fields
                )
                # PLOG and Chebyshev kinetics have no collider efficiencies.
                if created and getattr(rmg_kinetics_data, "efficiencies", None):
                    create_and_save_efficiencies(
                        kinetic_model, kinetics_instance, rmg_kinetics_data, models
                    )
                if created:
                    index_new_rows(models, kinetics=kinetics_instance)

                models.KineticsComment.objects.get_or_create(
                    kinetics=kinetics_instance,
                    kinetic_model=kinetic_model,
                    defaults={"comment": comment},
                )
            counts["imported"] += 1
        except Exception:
            counts["failed"] += 1
            logger.exception(f"Failed to import reaction {entry.label}")
    return counts


def import_thermo(thermo_path, kinetic_model, models):
    local_context = {
        "ThermoData": ThermoData,
        "Wilhoit": Wilhoit,
        "NASAPolynomial": NASAPolynomial,
        "NASA": NASA,
    }
    library = ThermoLibrary(label=kinetic_model.model_name)
    # NOTE: In order for this feature to run we have to be on "rmg-py/importer" branch, may require reinstall # noqa: E501
    library.SKIP_DUPLICATES = True
    library.load(thermo_path, local_context=local_context)
    for species_name, entry in library.entries.items():
        logger.info(f"Importing Thermo entry for {species_name}")
        try:
            species = get_or_create_species(kinetic_model, species_name, [entry.item], models)
            thermo_data = entry.data
            poly1, poly2 = thermo_data.polynomials

            # Sanitise temperature ranges: some RMG entries have 0 K break
            # temperatures or poly2.Tmin < poly1.Tmax (overlapping ranges).
            t_min_1 = poly1.Tmin.value_si
            t_max_1 = poly1.Tmax.value_si
            t_min_2 = poly2.Tmin.value_si
            t_max_2 = poly2.Tmax.value_si

            if t_max_1 == 0:
                t_max_1 = 1000.0
            if t_min_2 == 0:
                t_min_2 = 1000.0
            if t_min_2 < t_max_1:
                t_min_2 = t_max_1

            thermo, _ = models.Thermo.objects.get_or_create(
                species=species,
                coeffs_poly1=poly1.coeffs.tolist(),
                coeffs_poly2=poly2.coeffs.tolist(),
                temp_min_1=t_min_1,
                temp_max_1=t_max_1,
                temp_min_2=t_min_2,
                temp_max_2=t_max_2,
            )
            thermo_comment = models.ThermoComment.objects.create(
                kinetic_model=kinetic_model, thermo=thermo
            )
            thermo_comment.comment = entry.long_desc or entry.short_desc or thermo_comment.comment
            thermo.save()
            thermo_comment.save()
        except Exception:
            logger.exception("Failed to import entry")


def create_and_save_authorships(source, author_data, models):
    for order, author_datum in enumerate(author_data):
        firstname = author_datum.get("given")
        lastname = author_datum.get("family")
        author_fields = filter_fields({"firstname": firstname, "lastname": lastname})
        author, _ = models.Author.objects.get_or_create(**author_fields)
        authorship, _ = models.Authorship.objects.get_or_create(
            source=source, author=author, defaults={"order": order}
        )
        safe_save(author)
        safe_save(authorship)


def import_source(source_path, kinetic_model, models):
    crossref = habanero.Crossref(mailto="kianmehrabani@gmail.com")
    try:
        doi = get_doi(source_path)
        reference = crossref.works(ids=doi).get("message", "") if doi else {}
        created_info = reference.get("created", "")
        date = parser.parse(created_info.get("date-time", "")) if created_info else None
        year = date.year if date else ""
        title_body = reference.get("title", "")
        source_title = title_body[0] if isinstance(title_body, list) else title_body
        name_body = reference.get("short-container-title", "")
        journal_name = name_body[0] if isinstance(name_body, list) else name_body
        volume_number = reference.get("volume", "")
        page_numbers = reference.get("page", "")
        author_data = reference.get("author")
        fields = dict(
            publication_year=year,
            source_title=source_title,
            journal_name=journal_name,
            journal_volume_number=volume_number,
            page_numbers=page_numbers,
        )
        source, created = models.Source.objects.get_or_create(doi=doi)
        if created:
            for k, v in fields.items():
                setattr(source, k, v)

        source.kineticmodel_set.add(kinetic_model)
        source.save()
        # Only populate authorships for a freshly created source; an existing
        # source already has them, and re-adding would duplicate Authorship rows.
        if created and author_data is not None:
            create_and_save_authorships(source, author_data, models)
        elif author_data is None:
            logger.warning("Could not find author data")
    except FileNotFoundError:
        logger.warning("source.txt not found")


def get_doi(source_path):
    """
    Get the DOI from the source.txt file
    """

    with open(source_path, "r") as f:
        source = f.read()

    regex = re.compile(r"10.\d{4,9}/\S+")
    matched_list = regex.findall(source)
    matched_list = [d.rstrip(".") for d in matched_list]
    # There are sometimes other trailing characters caught up, like ) or ]
    # We should probably clean up the source.txt files
    # But let's try cleaning them here.

    def clean(doi):
        for opening, closing in ["()", "[]"]:
            if doi.endswith(closing):
                if doi.count(closing) - doi.count(opening) == 1:
                    # 1 more closing than opening
                    # remove the last closing
                    doi = doi[:-1]
        return doi

    matched_list = [clean(d) for d in matched_list]
    matched_set = set(matched_list)

    if len(matched_set) == 0:
        raise ValueError("DOI not found")
    elif len(matched_set) > 1:
        raise ValueError("Found multiple DOIS")
    else:
        return matched_list[0]


# def get_models(path, ignore_list=[]):
#     """
#     Walk the given `path` looking for libraries and source files.
#     Skips any paths that end with something in the skip_list
#     (eg. skip_list=['PCI2011/193-Mehl'])
#     Returns tuples of the following form:
#         model_name, thermo_library, kinetics_library, source_file
#     """

#     ignore_list.extend([".git", "translations", "modelComparer"])
#     root, dirs, _ = next(os.walk(path))
#     for dir in dirs:
#         pdir = Path(dir)
#         if pdir.name not in ignore_list:
#             rmg_model_name = pdir.name
#             thermo_path = root / pdir / "RMG-Py-thermo-library" / "ThermoLibrary.py"
#             kinetics_path = root / pdir / "RMG-Py-kinetics-library" / "reactions.py"
#             source_path = root / pdir / "source.txt"
#             yield rmg_model_name, str(thermo_path), str(kinetics_path), str(source_path)


def get_models(path, ignore_list=[]):
    """
    Walk the given `path` looking for libraries and source files.
    Skips any paths that end with something in the skip_list
    (eg. skip_list=['PCI2011/193-Mehl'])
    
    Handles both:
    - Direct models: folder/RMG-Py-thermo-library/ThermoLibrary.py
    - Nested models: folder/subfolder/RMG-Py-thermo-library/ThermoLibrary.py
    
    For nested models, the model_name is "parent/subfolder" (e.g., "CombFlame2013/17-Malewicki")
    
    Returns tuples of the following form:
        model_name, thermo_library, kinetics_library, source_file
    """
    
    ignore_list = ignore_list.copy()  # Don't modify the default parameter
    ignore_list.extend([".git", "translations", "modelComparer"])
    
    # Convert to Path object for better handling
    base_path = Path(path)
    
    # Check if path exists
    if not base_path.exists():
        logger.error(f"Path does not exist: {path}")
        return
    
    def check_model_dir(model_dir, model_name):
        """Check if a directory contains RMG libraries and return model info if valid."""
        thermo_path = model_dir / "RMG-Py-thermo-library" / "ThermoLibrary.py"
        kinetics_path = model_dir / "RMG-Py-kinetics-library" / "reactions.py"
        source_path = model_dir / "source.txt"
        
        # Check if this directory has the libraries
        if thermo_path.exists() or kinetics_path.exists():
            return (
                model_name,
                str(thermo_path) if thermo_path.exists() else None,
                str(kinetics_path) if kinetics_path.exists() else None,
                str(source_path) if source_path.exists() else None,
            )
        return None
    
    # Walk through directories
    try:
        for item in sorted(base_path.iterdir()):
            if not item.is_dir():
                continue
                
            if item.name in ignore_list:
                continue
            
            top_level_name = item.name
            
            # Check if this is in the ignore list (with path prefix)
            if any(skip in top_level_name for skip in ignore_list):
                continue
            
            # First, check if this directory itself is a model (has libraries directly)
            result = check_model_dir(item, top_level_name)
            if result:
                yield result
            else:
                # No direct libraries - check subdirectories for nested models
                for sub_dir in sorted(item.iterdir()):
                    if not sub_dir.is_dir():
                        continue
                    if sub_dir.name.startswith('.') or sub_dir.name in ignore_list:
                        continue
                    
                    # Create nested model name
                    nested_name = f"{top_level_name}/{sub_dir.name}"
                    
                    # Check if nested name is in ignore list
                    if any(skip in nested_name for skip in ignore_list):
                        logger.info(f"Skipping {nested_name} (in ignore list)")
                        continue
                    
                    result = check_model_dir(sub_dir, nested_name)
                    if result:
                        yield result
                        
    except Exception as e:
        logger.error(f"Error walking directory {path}: {e}")