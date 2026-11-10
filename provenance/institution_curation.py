"""The institutions of the experiments, checked by hand against the ROR registry (10 November 2026).

The ROR ids came from a lexical match (mappings/scripts/generate_sssom.py) that took the first
ROR search hit. Seven of them named another organisation: the Stanford High Temperature
Gasdynamics Laboratory got a volcanology laboratory in Italy and a laboratory in China, the
Sloan Automotive Laboratory of MIT got "Sloan*Longway", "Aachen University" got the university
hospital of Aachen, "University of California" got UC Merced, and the United Technologies
Research Center in East Hartford got the one in Cork (the East Hartford centre has no ROR record).

Each entry is the institution text of the ChemKED files:

* ``ror``      the ROR id of the organisation itself ("" when ROR has no record of it);
* ``same_as``  another spelling of the institution named there (the records are merged);
* ``parent``   the organisation that the lab or department is part of (the record links to it).

A lab or department has no ROR id of its own; its mapping is a skos:broadMatch to the ROR id of
the nearest parent that has one.
"""

CHECKED = "2026-11-10"

INSTITUTIONS = {
    # Stanford University: the High Temperature Gasdynamics Laboratory is in Mechanical Engineering.
    "Stanford University": {"ror": "00f54p054"},
    "Department of Mechanical Engineering, Stanford University": {"parent": "Stanford University"},
    "High Temperature Gasdynamics Laboratory, Department of Mechanical Engineering, Stanford University": {
        "parent": "Department of Mechanical Engineering, Stanford University"},
    "High Temperature Gasdynamics Laboratory, Stanford University": {
        "same_as": "High Temperature Gasdynamics Laboratory, Department of Mechanical Engineering, Stanford University"},
    "High Temperature Gas dynamics Laboratory, Mechanical Engineering Department, Stanford University": {
        "same_as": "High Temperature Gasdynamics Laboratory, Department of Mechanical Engineering, Stanford University"},
    # Rensselaer Polytechnic Institute
    "Rensselaer Polytechnic Institute": {"ror": "01rtyzb94"},
    "Rensselaer Polytechnic Institution": {"same_as": "Rensselaer Polytechnic Institute"},
    "Department of Mechanical, Aerospace, and Nuclear Engineering, Rensselaer Polytechnic Institute": {
        "parent": "Rensselaer Polytechnic Institute"},
    # University of Duisburg-Essen
    "University of Duisburg-Essen": {"ror": "04mz5ra38"},
    "Institute for Combustion and Gasdynamics, University of Duisburg-Essen": {"parent": "University of Duisburg-Essen"},
    # RWTH Aachen University: "Aachen University" is the shock tube of Zhang et al. 2016 (RWTH).
    "RWTH Aachen University": {"ror": "04xfq0f34"},
    "Aachen University": {"same_as": "RWTH Aachen University"},
    "Physico-Chemical Fundamentals of Combustion, RWTH Aachen University": {"parent": "RWTH Aachen University"},
    # MIT and ETH Zurich have no record of their own in the files: the curation adds them.
    "Massachusetts Institute of Technology": {"ror": "042nb2s44"},
    "Sloan Automotive Laboratory, M.I.T.": {"parent": "Massachusetts Institute of Technology"},
    "ETH Zurich": {"ror": "05a28rw58"},
    "Institute of Energy Technology, Zürich": {"parent": "ETH Zurich"},
    # The campus of Vermeer et al. 1972 is not in the file: the University of California System.
    "University of California": {"ror": "00pjdza24"},
    # The East Hartford centre (Colket 2001) has no ROR record; 04vxc1c96 is the centre in Cork.
    "United Technologies Research Center": {"ror": ""},
    # Checked and correct: NASA Lewis is now the Glenn Research Center, NUI Galway the University of Galway.
    "NASA Lewis Research Center; Cleveland, OH": {"ror": "059fqnc42"},
    "NUI Galway": {"ror": "03bea9k73"},
    "Case Western Reserve University": {"ror": "051fd9666"},
    "University of Connecticut": {"ror": "02der9h97"},
    "University of Michigan": {"ror": "00jmfr291"},
}

# The names of the organisations that ROR gives for the ids above (object_label of the mappings).
ROR_NAMES = {
    "00f54p054": "Stanford University",
    "01rtyzb94": "Rensselaer Polytechnic Institute",
    "04mz5ra38": "University of Duisburg-Essen",
    "04xfq0f34": "RWTH Aachen University",
    "042nb2s44": "Massachusetts Institute of Technology",
    "05a28rw58": "ETH Zurich",
    "00pjdza24": "University of California System",
    "059fqnc42": "Glenn Research Center",
    "03bea9k73": "Ollscoil na Gaillimhe – University of Galway",
    "051fd9666": "Case Western Reserve University",
    "02der9h97": "University of Connecticut",
    "00jmfr291": "University of Michigan",
}


def canonical_name(name):
    """The name of the record that ``name`` is a spelling of."""
    seen = set()
    while name in INSTITUTIONS and "same_as" in INSTITUTIONS[name] and name not in seen:
        seen.add(name)
        name = INSTITUTIONS[name]["same_as"]
    return name


def ror_mapping(name):
    """(ROR id, SSSOM predicate) for the institution text ``name``: skos:exactMatch for the
    organisation itself, skos:broadMatch to the nearest parent with a ROR id for a lab or
    department, ("", "") when there is none, None when the name is not curated."""
    if name not in INSTITUTIONS:
        return None
    current, predicate, seen = canonical_name(name), "skos:exactMatch", set()
    while current in INSTITUTIONS and current not in seen:
        seen.add(current)
        entry = INSTITUTIONS[current]
        if "ror" in entry:
            return (entry["ror"], predicate) if entry["ror"] else ("", "")
        current, predicate = entry.get("parent"), "skos:broadMatch"
    return ("", "")


def parent_of(name):
    return INSTITUTIONS.get(canonical_name(name), {}).get("parent")


def own_ror(name):
    """The ROR id of the record itself (not of a parent)."""
    return INSTITUTIONS.get(canonical_name(name), {}).get("ror", "")


def institution_for(name, created=None):
    """The record of the curated institution ``name`` (its canonical spelling), with its parents;
    the records that are missing are made. ``created`` collects the names of new records."""
    from provenance.models import Institution

    name = canonical_name(name)
    parent_name = parent_of(name)
    parent = institution_for(parent_name, created) if parent_name else None
    found = Institution.objects.filter(name=name).order_by("pk").first()
    if found is None:
        found = Institution.objects.create(name=name, parent=parent, ror_id=own_ror(name))
        if created is not None:
            created.append(name)
    return found
