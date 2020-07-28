import os
import re
import logging

import habanero
from django.db import migrations
from dateutil import parser
from requests.exceptions import HTTPError


def import_rmg_models(apps, schema_editor):
    model_names = ["Source"]
    models = {model_name: apps.get_model("database", model_name) for model_name in model_names}
    logging.basicConfig(filename="import_log.txt", level=logging.DEBUG)
    path = os.path.expanduser("~/RMG-models/")
    logging.info(f"path:{path}")
    skip_list = ["PCI2011/193-Mehl"]
    thermo_libs, kinetics_libs, source_paths = find_library_files(path, skip_list)
    logging.info("IMPORTING SOURCES")
    sources_successful = import_sources(source_paths, **models)
    logging.info(f"SOURCE COUNT: {len(source_paths)}")
    logging.info(f"SOURCE SUCCESSES: {sources_successful}")


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0020_auto_20200727_2124"),
    ]

    operations = [migrations.RunPython(import_rmg_models)]


def safe_save(instance):
    try:
        instance.save()
    except Exception as e:
        logging.error(e)


def import_sources(source_paths, **models):
    crossref = habanero.Crossref(mailto="kianmehrabani@gmail.com")
    sources_successful = 0
    for source_path in source_paths:
        logging.info(f"\nImporting Source {source_path}")
        doi = get_doi(source_path)
        name = name_from_path(source_path)
        if doi:
            try:
                reference = crossref.works(ids=doi).get("message")
                created = reference.get("created")
                date = parser.parse(created.get("date-time")) if created else None
                year = date.year
                title_body = reference.get("title")
                source_title = title_body[0] if isinstance(title_body, list) else title_body
                name_body = reference.get("short-container-title")
                journal_name = name_body[0] if isinstance(name_body, list) else name_body
                volume_number = reference.get("volume")
                page_numbers = reference.get("page")
                search_constraints = {
                    k: v
                    for k, v in dict(
                        name=name,
                        doi=doi,
                        publication_year=year,
                        source_title=source_title,
                        journal_name=journal_name,
                        journal_volume_number=volume_number,
                        page_numbers=page_numbers,
                    ).items()
                    if v is not None
                }
                source, created = models["Source"].objects.get_or_create(**search_constraints)
                if created:
                    sources_successful += 1
                    safe_save(source)
                else:
                    logging.info("Source already created, skipping...")

            except HTTPError as e:
                logging.error(e)

            except KeyError as e:
                logging.error(e)
        else:
            logging.warning("Failed to find DOI, skipping...")

    return sources_successful


def name_from_path(path):
    """
        Get the library name from the (full) path
        """
    name_path_re = re.compile("\.*\/?(.+?)\/RMG-Py-.*-library.*")
    match = name_path_re.match(path)
    if match:
        return match.group(1).split("RMG-models/")[-1]
    else:
        return os.path.split(path)[0]


def get_doi(source_path):
    """
    Get the DOI from the source.txt file
    """

    with open(source_path, "r") as f:
        source = f.read()
    regex = re.compile("10.\d{4,9}/\S+")

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
        matched_doi = None
    elif len(matched_set) > 1:
        logging.warning(f"Found multiple DOIS, choosing the first")
        matched_doi = matched_list[0]
    else:
        matched_doi = matched_list[0]

    return matched_doi


def find_library_files(path, skip_list=None):
    """
    Walk the given `path` looking for libraries and source files.
    Skips any paths that end with something in the skip_list
    (eg. skip_list=['PCI2011/193-Mehl'])
    Returns a 3-tuple:
        thermo_libraries, kinetics_libraries, source_files
    """
    skip_list = skip_list or []  # list of models to skip
    thermo_libraries = []
    kinetics_libraries = []
    source_files = []
    for root, dirs, files in os.walk(path):

        if any([root.strip("/").endswith(skip) for skip in skip_list]):
            logging.info(f"Skipping {root} because it is in the skip_list.")
            continue  # skip this one

        for name in files:
            path = os.path.join(root, name)
            if name == "source.txt":
                logging.info(f"Found source file {path}")
                source_files.append(path)
            elif root.endswith("RMG-Py-thermo-library") and name == "ThermoLibrary.py":
                logging.info(f"Found thermo library {path}")
                thermo_libraries.append(path)
            elif root.endswith("RMG-Py-kinetics-library") and name == "reactions.py":
                logging.info(f"Found kinetics file {path}")
                kinetics_libraries.append(path)
            else:
                logging.debug(
                    f"{path} unread because it is not named like a kinetics or thermo "
                    "library generated by the chemkin importer"
                )
    return thermo_libraries, kinetics_libraries, source_files
