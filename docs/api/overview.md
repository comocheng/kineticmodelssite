# API overview

All resources live under `/api/`. List endpoints are paginated, public to read, and
support [filtering, search, and ordering](filtering.md). The full, always-current
reference is the live [Swagger UI and ReDoc](../reference.md).

## Resource map

### Species & structures (`tags: species`)
| Endpoint | Description |
|----------|-------------|
| `/api/species/` | Canonical species (PrIMe ID, CAS, isomers) |
| `/api/isomer/` | Isomers (InChI) |
| `/api/formula/` | Molecular formulae |
| `/api/structure/` | Adjacency list / SMILES structures |

### Reactions, kinetics, thermo, transport
| Endpoint | Description |
|----------|-------------|
| `/api/reaction/` | Reactions (with stoichiometry) |
| `/api/kinetics/` | Rate-coefficient parameterizations |
| `/api/thermo/` | NASA-polynomial thermochemistry |
| `/api/transport/` | Transport properties |
| `/api/thermo-record/` | Thermochemistry source records (ATcT, Burcat, group additivity); see [Thermochemistry sources](../thermochemistry.md) |
| `/api/thermo-enrichment/` | Status of the thermochemistry source lookups |
| `/api/kineticmodel/` | Assembled kinetic models |

### Bibliography (`tags: bibliography`)
| Endpoint | Description |
|----------|-------------|
| `/api/source/` | Literature sources (DOI, journal, year) |
| `/api/author/` | Authors |

### Experimental data (`tags: experimental-data`, read-only)
| Endpoint | Description |
|----------|-------------|
| `/api/experiment-dataset/` | Datasets (apparatus, reference, authors, common properties) |
| `/api/experiment-datapoint/` | Datapoints (T, P, φ, composition) |
| `/api/ignition-delay/` | Ignition-delay measurements |
| `/api/laminar-burning-velocity/` | Laminar burning velocity |
| `/api/rate-coefficient/` | Direct rate-coefficient measurements |
| `/api/speciation-measurement/` | Speciation measurements (jet stirred reactor, flow reactor, flame, shock tube) with their profiles |
| `/api/concentration-profile/` | Species profiles of speciation measurements |
| `/api/auxiliary-profile/` | Temperature, pressure, volume or velocity profiles measured with the species |
| `/api/time-history/` | Signals measured against time for a datapoint (ChemKED `time-histories`, e.g. volume profiles); `/api/experiment-datapoint/?expand=time_histories` puts them inline |
| `/api/volume-history/` | Volume against time for a datapoint (ChemKED `volume-history`); `?expand=volume_history` on datapoints |
| `/api/apparatus/` | Apparatus (kind, mode, facility) |
| `/api/common-properties/` | Dataset-level common properties |
| `/api/composition/`, `/api/composition-species/` | Mixture compositions and species amounts |

### Analysis & agreement (`tags: analysis`, read-only)
| Endpoint | Description |
|----------|-------------|
| `/api/simulation-run/` | Simulation runs (model × dataset) |
| `/api/simulation-result/` | Aggregate run results (error/deviation functions) |
| `/api/datapoint-result/` | Per-datapoint simulated vs. experimental values |
| `/api/model-dataset-coverage/` | Which models cover which datasets |
| `/api/fuel-model-compatibility/` | Fuel ↔ model compatibility |
| `/api/species-mapping/`, `/api/fuel-group/`, `/api/fuel-species/` | Supporting tables |

### Contribution (`tags: contribute`, authenticated)
| Endpoint | Description |
|----------|-------------|
| `POST /api/contribute/` | Upload ChemKED/Chemkin files → open a PR |
| `GET /api/contribute/status/{pr_number}/` | Check contribution CI status |

See [Contributing data](../contributing-data.md).

### Provenance & FAIR metadata (`tags: provenance`, `metadata`, read-only)
| Endpoint | Description |
|----------|-------------|
| `/api/institution/`, `/api/person/`, `/api/license/` | Institutions (ROR), persons (ORCID) and licenses (SPDX) |
| `/api/external-identifier/` | Identifiers of a record in other schemes (InChI, InChIKey) |
| `/api/semantic-mapping/` | SSSOM mappings to other vocabularies and databases |
| `/api/metadata/`, `/api/{resource}/{id}/metadata/` | JSON-LD for the catalog, a source, a kinetic model or a dataset |

See [Provenance & FAIR metadata](provenance.md).
