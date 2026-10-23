# Contributing data

New experimental data enters the platform through an **authenticated upload that opens a
pull request** against the ChemKED dataset repository, where it is validated by CI before
merge. This keeps every contribution reviewed and provenance-tracked.

## Upload a file

```bash
curl -X POST "https://dev.omethe.us/api/contribute/" \
  -H "Authorization: Token <your-token>" \
  -F "contributor_name=Ada Lovelace" \
  -F "contributor_orcid=0000-0002-1825-0097" \
  -F "file_type=chemked" \
  -F "description=Shock-tube ignition delays for n-heptane" \
  -F "files=@my_dataset.yaml"
```

Fields:

| Field | Required | Notes |
|-------|----------|-------|
| `contributor_name` | yes | Display name |
| `contributor_orcid` | yes | `0000-0000-0000-000X` |
| `file_type` | yes | `chemked` or `chemkin` |
| `description` | no | PR description |
| `run_pyteck` | no | Trigger PyTeCK CI simulation |
| `import_to_db` | no | Also import to the local database after PR creation |
| `files` | yes | One or more files (repeat `-F "files=@..."`) |

ChemKED files are validated locally with PyKED before the PR is opened; invalid files are
rejected with per-file messages.

Each ChemKED file is placed where the repository layout puts files like it (fuel folder,
then the paper's `Author_Year` folder); the response lists the chosen `paths`. If the
repository already holds the same data under another name or folder, the pull request
updates that file instead of adding a copy.

## Check contribution status

```bash
curl -H "Authorization: Token <your-token>" \
  "https://dev.omethe.us/api/contribute/status/123/"
```

Returns the CI check-run statuses for the contribution's pull request.

## The ChemKED format

For the dataset schema and how experiments are represented, see
[`chemked_database/README.md`](https://github.com/LekiaAnonim/kineticmodelssite/blob/master/chemked_database/README.md).
