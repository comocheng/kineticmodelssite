# Drafts and pull requests to RMG-models

Every identification that an import job makes goes into RMG-models: first as a commit on the
model's draft branch on the server, then, when someone opens a pull request, to GitHub.

## How it works

1. **The read copy.** `RMGMODELSPATH` (`settings.RMG_MODELS_PATH`) is a git clone of
   RMG-models. Import jobs do not write to it. The evidence index, the downloads and the
   coverage pages read it. A deploy can check it out (`checkout -B`) at any time.
2. **A draft per model.** When a job starts, the Importer opens the draft of the job's model
   folder, or uses the one that is already open. A draft is:
   - a branch `importer/<folder>/<id>`, made from `origin/master`;
   - a worktree at `RMG_MODELS_WORKSPACES_PATH/<id>-<folder>`, with a sparse checkout of the
     model folder only.

   The vote databases of the folder in the read copy are copied into the draft. A model folder
   has at most one open draft.
3. **The job runs in the draft.** The importer works as before: it adds each confirmation to
   `SMILES.txt` and rewrites the two RMG-Py libraries.
4. **Checkpoint commits.**
   - `SMILES.txt` and `SMILES-BLOCKED.txt` are committed within a minute of a change, and again
     at the end of the run.
   - The libraries are committed only when the importer last reported `awaiting_input`,
     `finished` or `stopped`, because it empties the library folder before it writes it.
   - `progress.json`, `importer_state.json`, the vote databases and the logs are never committed.
   - The logs are not in the draft: each job keeps `output.log`, `error.log` and a copy of `RMG.log`
     in `IMPORTER_LOGS_PATH/<job id>/`, so they stay after the draft closes. Logs of runs from
     before that are copied in with `manage.py collect_job_logs --from <RMG-models folder> --apply`.
   - The author is the person who started the job (their GitHub account, if it is connected).
     The committer is `IMPORTER_GIT_NAME <IMPORTER_GIT_EMAIL>`.
5. **The job page** ("Changes in RMG-models") shows:
   - the branch, commits, `SMILES.txt` lines added and removed, changed files, and files not yet
     committed;
   - **Open pull request** / **Update pull request #N**;
   - **Discard draft**.
6. **Pull request.**
   - The person connects their own GitHub account, through the Prometheus GitHub App.
   - **Open pull request** commits what is left, pushes the branch with that person's token, and
     opens a pull request into master. **Update pull request #N** pushes new commits to it.
   - The button is disabled, with the reason shown, when:
     - the job is not Completed or Cancelled;
     - the draft is the same as master;
     - the pull request already has every commit;
     - the person has no write access to RMG-models.
   - Nothing is pushed to master directly.
7. **After the merge.** The App's webhook (a "Pull request" event) closes the draft within
   seconds of the merge; the job page also reads the pull request's state (at most every
   5 minutes), in case a delivery is lost. A merged pull request:
   - deletes the draft's branch on GitHub with the token of the person who pushed it, as
     GitHub's **Automatically delete head branches** setting does. A branch that has commits
     pushed after the merge is kept; a branch that is already deleted is fine;
   - closes the draft: its worktree and local branch are removed;
   - waits while a job runs in the draft (the worktree is its folder), and is done at the first
     check after the job stops.

   The next start opens a new draft from master. The read copy follows master by itself (see
   "Updates from GitHub"). Loading the merged model into the database (`import_rmg_models`,
   `rebuild_model_links`) is still a separate step.

## Adding a model

`/kineticmodel/create/` ("Add a model to the Importer", also the **Add a model** button on the
dashboard) puts a new model's files into a new draft, in the folder template of an import job:

| File | What it is |
| --- | --- |
| `mechanism.txt` | the uploaded mechanism (the `--species` and `--reactions` file) |
| `thermo.txt` | the uploaded thermo file; no file if the thermo is in the mechanism |
| `transport.txt` | the uploaded transport file, if any |
| `SMILES.txt` | the uploaded SMILES.txt, or an empty file |
| `source.txt` | the citation, `DOI: https://doi.org/...`, `Downloaded from <page>` if the files did not come with the paper, the original file names, and who added the model |
| `import.sh` | written by Prometheus, with no port and no SBATCH lines |

- The files are kept byte for byte. The first commit is "<folder>: add the model files as
  uploaded", by the person who added them.
- `source.txt` can name one DOI only, because `import_rmg_models` looks the paper up by it.
- **Create and import** runs Check files, then sends you to the Importer job page. The import
  starts when the check passes. If it fails, the job page says so and links the Files tab.
- No KineticModel row is made. The model goes into the database after its pull request is
  merged (`import_rmg_models`), in the same way as ChemKED datasets.

## Editing a model's files

The **Files** tab of a job lists the files of its draft. If the job has no draft, select **Open a
draft to edit the files**.

- `SMILES.txt`, `source.txt` and the CHEMKIN files, up to 5 MB each, are edited in the browser:
  1. Select **Preview the change** to see the diff.
  2. Select **Commit**. The commit message is required, and the commit is on the draft's branch,
     with your name.
  - A file keeps its encoding (UTF-8 or Latin-1) and its line ends (LF or CRLF).
  - Before a `SMILES.txt` is saved, its format is checked: two words per line, no species given
    two SMILES. Names that are not species of the mechanism give a warning.
- Larger files, and new files (for example `transport.txt`), are uploaded. The file is kept
  byte for byte.
- `import.sh`, the RMG-Py libraries and the files the importer writes are not edited here.
- While the job is pending, running or awaiting input, the files can be read but not changed.
- **Check files** runs `importChemkin.py --minimal` on the draft. It reads the species, thermo,
  `SMILES.txt` (formulas and spin notation, with the importer's own rules) and reactions, then
  stops. Its log goes outside the model folder, so the job's `RMG.log` stays.

When the files are ready, start the job from the same page. Its identifications go to the same
branch. Then open the pull request.

## Server set-up

- The read copy must have the remote `origin` = `comocheng/RMG-models`, and must be able to
  `git fetch origin master` (as it does now). Without network access a draft starts from the
  last fetched `origin/master`, and the page says so.
- Settings (`.env`), with their defaults:

  | Setting | Default |
  | --- | --- |
  | `IMPORTER_WORKSPACES` | `true`; `false` runs jobs in the read copy, with no commits, as before |
  | `RMG_MODELS_WORKSPACES_PATH` | `RMG-models-drafts` next to the read copy |
  | `RMG_MODELS_REMOTE` | `origin` |
  | `RMG_MODELS_BASE_BRANCH` | `master` |
  | `RMG_MODELS_GITHUB_REPO` | `comocheng/RMG-models` |
  | `IMPORTER_GIT_NAME` | `Prometheus Importer` |
  | `IMPORTER_GIT_EMAIL` | `importer@pr.omethe.us` |
  | `GITHUB_APP_CLIENT_ID` | none; required for pull requests |
  | `GITHUB_APP_CLIENT_SECRET` | none; required for pull requests |
  | `GITHUB_TOKEN_ENCRYPTION_KEY` | a key derived from `SECRET_KEY` |
  | `PUBLIC_SITE_URL` | none; set it to `https://pr.omethe.us`, so the callback address is the https one registered with the App |
  | `GITHUB_WEBHOOK_SECRET` | none; the App's webhook secret. Empty: `/importer/github/webhook/` is off |
  | `IMPORTER_LOGS_PATH` | `importer-logs` next to the read copy; each job's `output.log`, `error.log` and a copy of `RMG.log`, in `<path>/<job id>/` |

  For `GITHUB_TOKEN_ENCRYPTION_KEY`, make a key with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  If the key changes, people connect GitHub again.
- Migrations: `importer_dashboard` 0020 (drafts) and 0021 (GitHub accounts, pull requests).
- Drafts start from master. Merge the RMG-models fix branches that production uses
  (`fix/sun-ch2oh-merges` and the others) into master first.

## The GitHub App

A comocheng owner must do these steps.

1. Make the App: GitHub, then **Settings**, then **Developer settings**, then **GitHub Apps**,
   then **New GitHub App** (for the comocheng organisation).
   - Name: for example "Prometheus Importer". Homepage: https://pr.omethe.us.
   - Callback URL: `https://pr.omethe.us/importer/github/callback/`.
   - Select **Expire user authorization tokens**.
   - Do not select **Request user authorization (OAuth) during installation**.
   - Webhook: see "Updates from GitHub" below.
   - Repository permissions: **Contents** read and write; **Pull requests** read and write;
     **Metadata** read (it is always on).
   - Where can this App be installed: **Only on this account**.
2. Make a client secret. Put the client ID and the secret in the server's `.env` as
   `GITHUB_APP_CLIENT_ID` and `GITHUB_APP_CLIENT_SECRET`. No private key is necessary: the
   Importer uses only user access tokens.
3. Install the App on comocheng, for the repository **RMG-models** only.
4. Set `PUBLIC_SITE_URL=https://pr.omethe.us` in `.env` too. Behind nginx, Django can see the
   request as http, and GitHub refuses a callback that is not the registered https one.
5. Restart gunicorn. Each person then selects **Connect GitHub** on a job page once.

A user access token can do only what both the App and the person can do. People without write
access to RMG-models see a disabled button with the reason.

## Updates from GitHub

When a pull request is merged into RMG-models master on GitHub, the read copy on the server moves
to the new master by a **fast-forward only** (`importer_dashboard/read_copy_sync.py`). It is
never merged, reset or cleaned. It is not moved, and the reason is kept, when:

- the read copy is on another branch than master;
- a tracked file has a change that nobody committed;
- it has commits that master does not have;
- git cannot fast-forward (for example, an untracked file is where master adds one);
- drafts are off and an import job is running in the read copy.

After a move, the evidence index is refreshed. The database is not changed (`import_rmg_models`).

Three things start it:

1. **The App's webhook**, within seconds of a merge. A comocheng owner sets it up:
   - Make a secret: `python3 -c "import secrets; print(secrets.token_hex(32))"`.
   - App settings, **General**, **Webhook**: select **Active**. Webhook URL:
     `https://pr.omethe.us/importer/github/webhook/`. Webhook secret: the secret. Keep SSL
     verification on.
   - **Permissions & events**, **Subscribe to events**: select **Push** and **Pull request**.
     (They use the Contents and Pull requests permissions that the App already has.)
   - Put the same secret in the server's `.env` as `GITHUB_WEBHOOK_SECRET`, and restart gunicorn.
   - The webhook accepts only deliveries signed with the secret (`X-Hub-Signature-256`). It
     answers GitHub's ping, queues the update for a push to `RMG_MODELS_GITHUB_REPO`'s
     `RMG_MODELS_BASE_BRANCH`, queues the close of an open draft whose pull request was merged
     (`close_merged_draft`), and ignores other pushes, pull requests and events. Its answer is under
     **Advanced**, **Recent deliveries** in the App settings, where a delivery can be sent again.
2. **Celery Beat, every 15 minutes**, in case a delivery is lost (`sync-rmg-models-read-copy`).
3. **Update now** on the Importer Settings page (superusers only), which also shows the read copy's
   branch and commit and the result of the last check.

The read copy must be on master for any of these to move it. On production it is on
`fix/sun-ch2oh-merges` until the fix branches are merged into master.

## Before the first job in a draft on production (read-only checks)

```bash
RMG=/home/prometheus/Importer/RMG-models
git -C "$RMG" status --short | head -50
git -C "$RMG" log -1 --oneline
grep -c -v -E '^\s*(!|$)' "$RMG/AramcoMech_2.0/SMILES.txt"   # GitHub master has 493
ls "$RMG"/*/votes_*.db "$RMG"/*/*/votes_*.db 2>/dev/null | head
```

Uncommitted identifications in the read copy are not moved into drafts automatically. Their
vote databases are copied, so the importer offers again, as tentative matches, the
identifications that the vote database has and `SMILES.txt` does not (RMG-Py change "Offer
identifications that only the vote database has as tentative matches").

## Celery

The task commits while it waits for its importer. The status refresh, on every dashboard and job
page view and every 30 seconds from Celery Beat, commits for jobs that are awaiting input. Celery
Beat's refresh runs on the default queue. If two imports use both worker slots, it waits, and
then only page views make checkpoints. A separate queue for `refresh_all_job_statuses`, with its
own worker, would remove this wait.
