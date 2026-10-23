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
| `/api/concentration-time-profile/` | Concentration–time profiles |
| `/api/jet-stirred-reactor/` | Jet-stirred reactor speciation |
| `/api/outlet-concentration/` | Outlet concentration |
| `/api/burner-stabilized-flame/` | Burner-stabilized flame speciation |
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
