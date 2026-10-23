import time

from django.contrib.auth.decorators import login_required
from django.db import connections, OperationalError, ProgrammingError
from django.shortcuts import render

from .forms import QueryForm

# Tables surfaced in the schema sidebar, grouped by app
SCHEMA_GROUPS = {
    "database": [
        "database_kineticmodel",
        "database_source",
        "database_author",
        "database_species",
        "database_reaction",
        "database_transport",
        "database_thermo",
        "database_speciesname",
    ],
    "chemked_database": [
        "chemked_datasets",
        "chemked_datapoints",
        "chemked_ignition_delay",
        "chemked_flame_speed",
        "chemked_apparatus",
        "chemked_compositions",
        "chemked_composition_species",
    ],
    "importer_dashboard": [
        "importer_dashboard_importtask",
        "importer_dashboard_importedfile",
    ],
    "analysis": [
        "analysis_simulation_run",
    ],
}

# ---------------------------------------------------------------------------
# Query examples — shown in the UI for quick exploration
# Each entry: {"category": str, "label": str, "sql": str}
# ---------------------------------------------------------------------------
QUERY_EXAMPLES = [
    # ── Kinetic Models ──────────────────────────────────────────────────
    {
        "category": "Kinetic Models",
        "label": "All models with source paper",
        "sql": (
            "SELECT km.id, km.model_name, s.source_title, s.publication_year, s.journal_name\n"
            "FROM database_kineticmodel km\n"
            "LEFT JOIN database_source s ON km.source_id = s.id\n"
            "ORDER BY s.publication_year DESC\n"
            "LIMIT 50"
        ),
    },
    {
        "category": "Kinetic Models",
        "label": "Species count per model",
        "sql": (
            "SELECT km.model_name,\n"
            "       COUNT(DISTINCT sn.species_id) AS species_count\n"
            "FROM database_kineticmodel km\n"
            "LEFT JOIN database_speciesname sn ON sn.kinetic_model_id = km.id\n"
            "GROUP BY km.id, km.model_name\n"
            "ORDER BY species_count DESC\n"
            "LIMIT 30"
        ),
    },
    {
        "category": "Kinetic Models",
        "label": "Reactions (kinetics entries) per model",
        "sql": (
            "SELECT km.model_name,\n"
            "       COUNT(kc.kinetics_id) AS reaction_count\n"
            "FROM database_kineticmodel km\n"
            "LEFT JOIN database_kineticscomment kc ON kc.kinetic_model_id = km.id\n"
            "GROUP BY km.id, km.model_name\n"
            "ORDER BY reaction_count DESC\n"
            "LIMIT 30"
        ),
    },
    {
        "category": "Kinetic Models",
        "label": "Models with both thermo and kinetics imported",
        "sql": (
            "SELECT km.model_name,\n"
            "       COUNT(DISTINCT tc.thermo_id)   AS thermo_entries,\n"
            "       COUNT(DISTINCT kc.kinetics_id) AS kinetics_entries\n"
            "FROM database_kineticmodel km\n"
            "LEFT JOIN database_thermocomment   tc ON tc.kinetic_model_id = km.id\n"
            "LEFT JOIN database_kineticscomment kc ON kc.kinetic_model_id = km.id\n"
            "GROUP BY km.id, km.model_name\n"
            "ORDER BY kinetics_entries DESC\n"
            "LIMIT 30"
        ),
    },
    # ── Species & Kinetics ───────────────────────────────────────────────
    {
        "category": "Species & Kinetics",
        "label": "Species appearing in the most models",
        "sql": (
            "SELECT sn.name,\n"
            "       COUNT(DISTINCT sn.kinetic_model_id) AS model_count\n"
            "FROM database_speciesname sn\n"
            "WHERE sn.name != '' AND sn.kinetic_model_id IS NOT NULL\n"
            "GROUP BY sn.name\n"
            "ORDER BY model_count DESC\n"
            "LIMIT 30"
        ),
    },
    {
        "category": "Species & Kinetics",
        "label": "Enthalpy of formation at 298 K (from NASA7 coefficients)",
        "sql": (
            "-- H298 computed from NASA7 poly1 coefficients (R=8.31446 J/mol/K, T=298.15 K)\n"
            "-- Most exothermic species (largest negative Hf) appear first\n"
            "WITH best_thermo AS (\n"
            "  SELECT DISTINCT ON (sn.name) sn.name,\n"
            "         ROUND(\n"
            "           8.31446 * (\n"
            "               t.coeffs_poly1[1] * 298.15\n"
            "             + t.coeffs_poly1[2] * 298.15^2 / 2.0\n"
            "             + t.coeffs_poly1[3] * 298.15^3 / 3.0\n"
            "             + t.coeffs_poly1[4] * 298.15^4 / 4.0\n"
            "             + t.coeffs_poly1[5] * 298.15^5 / 5.0\n"
            "             + t.coeffs_poly1[6]\n"
            "           )::numeric / 1000, 2\n"
            "         ) AS hf_kJ_per_mol,\n"
            "         t.temp_min_1 AS T_low_K,\n"
            "         t.temp_max_2 AS T_high_K\n"
            "  FROM database_thermo t\n"
            "  JOIN database_speciesname sn ON sn.species_id = t.species_id\n"
            "  WHERE sn.name != ''\n"
            "    AND t.coeffs_poly1 IS NOT NULL\n"
            "    AND 298.15 BETWEEN t.temp_min_1 AND t.temp_max_1\n"
            "  ORDER BY sn.name\n"
            ")\n"
            "SELECT * FROM best_thermo\n"
            "ORDER BY hf_kJ_per_mol ASC\n"
            "LIMIT 50"
        ),
    },
    {
        "category": "Species & Kinetics",
        "label": "Kinetics rate-law types distribution",
        "sql": (
            "SELECT raw_data->>'type' AS kinetics_type,\n"
            "       COUNT(*)          AS count\n"
            "FROM database_kinetics\n"
            "GROUP BY raw_data->>'type'\n"
            "ORDER BY count DESC"
        ),
    },
    {
        "category": "Species & Kinetics",
        "label": "Arrhenius A-factor & activation energy (all reactions)",
        "sql": (
            "SELECT k.id,"
            " k.reaction_id,\n"
            "       (k.raw_data->>'a_si')::float  AS A_SI,\n"
            "       (k.raw_data->>'n')::float     AS n,\n"
            "       (k.raw_data->>'e_si')::float  AS Ea_J_per_mol,\n"
            "       k.min_temp, k.max_temp\n"
            "FROM database_kinetics k\n"
            "WHERE k.raw_data->>'type' = 'arrhenius'\n"
            "ORDER BY k.reaction_id\n"
            "LIMIT 50"
        ),
    },
    # ── Literature ───────────────────────────────────────────────────────
    {
        "category": "Literature",
        "label": "Models published per year",
        "sql": (
            "SELECT s.publication_year,\n"
            "       COUNT(*) AS model_count\n"
            "FROM database_kineticmodel km\n"
            "JOIN database_source s ON km.source_id = s.id\n"
            "WHERE s.publication_year != ''\n"
            "GROUP BY s.publication_year\n"
            "ORDER BY s.publication_year"
        ),
    },
    {
        "category": "Literature",
        "label": "Most prolific authors (by Source count)",
        "sql": (
            "SELECT a.lastname, a.firstname,\n"
            "       COUNT(au.source_id) AS source_count\n"
            "FROM database_author a\n"
            "JOIN database_authorship au ON au.author_id = a.id\n"
            "GROUP BY a.id, a.lastname, a.firstname\n"
            "ORDER BY source_count DESC\n"
            "LIMIT 20"
        ),
    },
    {
        "category": "Literature",
        "label": "Sources with most kinetic models",
        "sql": (
            "SELECT s.source_title, s.publication_year,\n"
            "       COUNT(km.id) AS model_count\n"
            "FROM database_source s\n"
            "JOIN database_kineticmodel km ON km.source_id = s.id\n"
            "GROUP BY s.id, s.source_title, s.publication_year\n"
            "ORDER BY model_count DESC\n"
            "LIMIT 20"
        ),
    },
    # ── Experimental Data (ChemKED) ───────────────────────────────────────
    {
        "category": "Experimental Data",
        "label": "Dataset count by experiment type",
        "sql": (
            "SELECT experiment_type,\n"
            "       COUNT(*) AS dataset_count\n"
            "FROM chemked_datasets\n"
            "GROUP BY experiment_type\n"
            "ORDER BY dataset_count DESC"
        ),
    },
    {
        "category": "Experimental Data",
        "label": "Ignition-delay datapoints by apparatus kind",
        "sql": (
            "SELECT a.kind,\n"
            "       COUNT(id_dp.id)                              AS datapoint_count,\n"
            "       ROUND(AVG(id_dp.ignition_delay)::numeric, 6) AS avg_delay_s\n"
            "FROM chemked_ignition_delay id_dp\n"
            "JOIN chemked_datapoints dp ON id_dp.datapoint_id = dp.id\n"
            "JOIN chemked_datasets   ds ON dp.dataset_id = ds.id\n"
            "JOIN chemked_apparatus   a ON ds.apparatus_id = a.id\n"
            "GROUP BY a.kind\n"
            "ORDER BY datapoint_count DESC"
        ),
    },
    {
        "category": "Experimental Data",
        "label": "Datasets by reference year and DOI",
        "sql": (
            "SELECT reference_doi, reference_year, experiment_type,\n"
            "       COUNT(*) AS dataset_count\n"
            "FROM chemked_datasets\n"
            "WHERE reference_doi != ''\n"
            "GROUP BY reference_doi, reference_year, experiment_type\n"
            "ORDER BY reference_year DESC, dataset_count DESC\n"
            "LIMIT 30"
        ),
    },
    {
        "category": "Experimental Data",
        "label": "Fuel composition species (most common fuels)",
        "sql": (
            "SELECT cs.species_name,\n"
            "       COUNT(*) AS appearance_count\n"
            "FROM chemked_composition_species cs\n"
            "WHERE cs.species_name NOT IN ('O2','N2','Ar','He','CO2','H2O')\n"
            "GROUP BY cs.species_name\n"
            "ORDER BY appearance_count DESC\n"
            "LIMIT 30"
        ),
    },
    # ── Simulation Results ────────────────────────────────────────────────
    {
        "category": "Simulation Results",
        "label": "Pass/fail rates per model",
        "sql": (
            "SELECT km.model_name,\n"
            "       COUNT(*)  AS total_runs,\n"
            "       SUM(CASE WHEN sr.status = 'completed' THEN 1 ELSE 0 END) AS completed,\n"
            "       SUM(CASE WHEN sr.status = 'failed'    THEN 1 ELSE 0 END) AS failed,\n"
            "       ROUND(\n"
            "         100.0 * SUM(CASE WHEN sr.status = 'completed' THEN 1 ELSE 0 END)\n"
            "               / NULLIF(COUNT(*), 0), 1\n"
            "       ) AS success_pct\n"
            "FROM analysis_simulation_run sr\n"
            "JOIN database_kineticmodel km ON sr.kinetic_model_id = km.id\n"
            "GROUP BY km.id, km.model_name\n"
            "ORDER BY total_runs DESC\n"
            "LIMIT 30"
        ),
    },
    {
        "category": "Simulation Results",
        "label": "Average simulation duration per model",
        "sql": (
            "SELECT km.model_name,\n"
            "       COUNT(*) AS run_count,\n"
            "       ROUND(AVG(EXTRACT(EPOCH FROM (sr.completed_at - sr.started_at)))::numeric, 1)\n"
            "         AS avg_duration_s,\n"
            "       MAX(EXTRACT(EPOCH FROM (sr.completed_at - sr.started_at)))\n"
            "         AS max_duration_s\n"
            "FROM analysis_simulation_run sr\n"
            "JOIN database_kineticmodel km ON sr.kinetic_model_id = km.id\n"
            "WHERE sr.status = 'completed'\n"
            "  AND sr.started_at IS NOT NULL\n"
            "  AND sr.completed_at IS NOT NULL\n"
            "GROUP BY km.id, km.model_name\n"
            "ORDER BY avg_duration_s DESC\n"
            "LIMIT 20"
        ),
    },
    {
        "category": "Simulation Results",
        "label": "Recent failed simulations with error preview",
        "sql": (
            "SELECT km.model_name,\n"
            "       sr.created_at,\n"
            "       LEFT(sr.error_message, 200) AS error_preview\n"
            "FROM analysis_simulation_run sr\n"
            "JOIN database_kineticmodel km ON sr.kinetic_model_id = km.id\n"
            "WHERE sr.status = 'failed' AND sr.error_message != ''\n"
            "ORDER BY sr.created_at DESC\n"
            "LIMIT 20"
        ),
    },
    {
        "category": "Simulation Results",
        "label": "Models never simulated against any dataset",
        "sql": (
            "SELECT km.id, km.model_name\n"
            "FROM database_kineticmodel km\n"
            "WHERE NOT EXISTS (\n"
            "  SELECT 1 FROM analysis_simulation_run sr\n"
            "  WHERE sr.kinetic_model_id = km.id\n"
            ")\n"
            "ORDER BY km.model_name"
        ),
    },
]

# Group examples by category for the template
QUERY_EXAMPLES_BY_CATEGORY: dict = {}
for _ex in QUERY_EXAMPLES:
    QUERY_EXAMPLES_BY_CATEGORY.setdefault(_ex["category"], []).append(_ex)


def _get_table_columns(table_name: str):
    """Return column names for *table_name*, empty list on any error."""
    try:
        with connections["default"].cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                [table_name],
            )
            return [row[0] for row in cur.fetchall()]
    except Exception:
        return []


# @login_required
def query_console(request):
    form = QueryForm(request.POST or None)
    columns: list[str] = []
    rows: list[tuple] = []
    row_count = None
    execution_time_ms = None
    error = None
    sql_executed = None

    if request.method == "POST" and form.is_valid():
        sql = form.cleaned_data["sql"]
        row_limit = form.cleaned_data["row_limit"]
        sql_executed = sql

        try:
            with connections["default"].cursor() as cursor:
                # Enforce a 10-second server-side timeout for the single statement
                cursor.execute("SET LOCAL statement_timeout = '10s'")

                t0 = time.perf_counter()
                cursor.execute(sql)
                elapsed = time.perf_counter() - t0
                execution_time_ms = round(elapsed * 1000, 2)

                if cursor.description:
                    columns = [col.name for col in cursor.description]
                    rows = cursor.fetchmany(row_limit)
                    row_count = len(rows)

        except (OperationalError, ProgrammingError) as exc:
            error = str(exc).strip()
        except Exception as exc:
            error = f"Unexpected error: {exc}"

    # Build schema sidebar: only include tables that actually exist in the DB
    schema = {}
    for group, tables in SCHEMA_GROUPS.items():
        group_data = {}
        for table in tables:
            cols = _get_table_columns(table)
            if cols:
                group_data[table] = cols
        if group_data:
            schema[group] = group_data

    context = {
        "form": form,
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
        "execution_time_ms": execution_time_ms,
        "error": error,
        "sql_executed": sql_executed,
        "schema": schema,
        "query_examples": QUERY_EXAMPLES_BY_CATEGORY,
    }
    return render(request, "livequery/query_console.html", context)
