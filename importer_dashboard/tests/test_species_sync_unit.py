"""
A job page lists the species of its vote database without anyone pressing Update progress, a
draft's votes outlive the draft, and a model merged into RMG-models becomes an import job.

On production (Nov 2026) ANL-Brown showed 210 of 210 species confirmed (its progress.json) but no
species rows, because only Update progress of a running job copied the vote database; and
POLIMI-NUIG-C4, merged into RMG-models master, had no import job.
"""
import os
import sqlite3
from unittest.mock import patch

from django.urls import reverse

from importer_dashboard import drafts, read_copy_sync, species_sync
from importer_dashboard.incremental_sync import IncrementalSync
from importer_dashboard.local_job_manager import LocalJobManager
from importer_dashboard.models import ClusterJob, DraftStatus, ImportJobStatus, SyncLog
from importer_dashboard.tasks import sync_job_species
from importer_dashboard.tests.test_drafts_unit import DraftTestCase, out, run
from importer_dashboard.tests.test_job_status_unit import JobStatusTestCase

SCHEMA = os.path.join(os.path.dirname(__file__), 'fixtures', 'vote_db_schema.sql')
SPECIES = [('AR', 'Ar', '[Ar]'), ('C2H4', 'C2H4', 'C=C'), ('CH4', 'CH4', 'C')]


def make_vote_database(folder, species=SPECIES, name='votes_0123.db'):
    path = os.path.join(folder, name)
    with sqlite3.connect(path) as db:
        db.executescript(open(SCHEMA).read())
        db.execute("INSERT INTO import_jobs (job_id, model_name, total_species, identified_species) "
                   "VALUES ('run', 'model', ?, ?)", (len(species), len(species)))
        for index, (label, formula, smiles) in enumerate(species):
            db.execute("INSERT INTO identified_species (job_id, chemkin_label, chemkin_formula, "
                       "rmg_species_label, rmg_species_smiles, rmg_species_index, identified_by) "
                       "VALUES ('run', ?, ?, ?, ?, ?, 'lekia')", (label, formula, label, smiles, index))
    return path


def run_now(job_id):
    """sync_job_species.delay, but in this process, as a worker would run it."""
    return sync_job_species.apply(args=[job_id])


class SpeciesRowsTests(JobStatusTestCase):
    def test_a_job_page_with_no_species_rows_loads_them_from_the_vote_database(self):
        make_vote_database(self.folder)
        page = reverse('importer_dashboard:job_detail', args=[self.job.id])
        with patch('importer_dashboard.tasks.sync_job_species.delay', side_effect=run_now) as delay:
            first = self.client.get(page)
        delay.assert_called_once_with(self.job.pk)
        self.assertContains(first, "Loading the species from this job's vote database")
        self.assertEqual(sorted(self.job.species.values_list('chemkin_label', flat=True)), ['AR', 'C2H4', 'CH4'])
        second = self.client.get(page)
        self.assertNotContains(second, 'Loading the species')
        self.assertContains(second, 'C=C')

    def test_the_end_of_a_run_queues_the_sync(self):
        make_vote_database(self.folder)
        with patch('importer_dashboard.tasks.species_sync.queue') as queue:
            self.run_job()
        queue.assert_called_once()
        self.assertEqual((queue.call_args.args[0].pk, queue.call_args.kwargs), (self.job.pk, {'force': True}))

    def test_live_jobs_are_synced_at_most_every_5_minutes(self):
        make_vote_database(self.folder)
        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.AWAITING_INPUT)
        with patch('importer_dashboard.tasks.sync_job_species.delay') as delay, \
                patch.object(LocalJobManager, '_refresh_detached_job'):
            LocalJobManager(config=self.config).refresh_statuses()
            delay.assert_called_once_with(self.job.pk)
            SyncLog.objects.create(job=self.job, sync_type='incremental', success=True)
            LocalJobManager(config=self.config).refresh_statuses()
            delay.assert_called_once()  # not again within 5 minutes

    def test_a_failed_sync_says_why_and_waits(self):
        make_vote_database(self.folder)
        with patch('importer_dashboard.incremental_sync.sync_job_votes',
                   return_value={'success': False, 'error': 'sqlite3: not found'}), \
                patch('importer_dashboard.tasks.sync_job_species.delay', side_effect=run_now):
            self.client.get(reverse('importer_dashboard:job_detail', args=[self.job.id]))
            response = self.client.get(reverse('importer_dashboard:job_detail', args=[self.job.id]))
        self.assertContains(response, "Could not load the species from this job's vote database: sqlite3: not found")

    def test_without_a_vote_database_nothing_is_queued(self):
        with patch('importer_dashboard.tasks.sync_job_species.delay') as delay:
            response = self.client.get(reverse('importer_dashboard:job_detail', args=[self.job.id]))
        delay.assert_not_called()
        self.assertContains(response, 'No species data yet')


class DraftVotesTests(DraftTestCase):
    def test_the_sync_reads_the_vote_database_of_the_open_draft(self):
        draft, _ = self.open()
        self.job.draft = draft
        self.job.save(update_fields=['draft'])
        sync = IncrementalSync(LocalJobManager(config=self.config), self.job)
        self.assertEqual(sync.job_path, os.path.join(draft.path, self.model))

    def test_closing_a_draft_keeps_its_votes_in_the_read_copy(self):
        draft, _ = self.open()
        make_vote_database(os.path.join(draft.path, self.model), species=SPECIES[:2])
        drafts.close_draft(draft, DraftStatus.MERGED)
        kept = os.path.join(self.read, self.model, 'votes_0123.db')
        with sqlite3.connect(kept) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM identified_species').fetchone()[0], 2)
        # No tracked file changes (RMG-models' .gitignore lists votes_*.db)
        self.assertEqual(out('status', '--porcelain', '--untracked-files=no', cwd=self.read), '')
        # The next draft of the model starts with these votes
        draft, _ = self.open()
        self.assertTrue(os.path.exists(os.path.join(draft.path, self.model, 'votes_0123.db')))


class NewModelTests(DraftTestCase):
    def setUp(self):
        super().setUp()
        run('checkout', '-q', 'master', cwd=self.read)
        self.seed = os.path.join(self.tmp.name, 'seed')
        ClusterJob.objects.create(name='PCI2019/555-Sun', config=self.config, status=ImportJobStatus.IDLE)

    def test_a_model_merged_on_github_becomes_an_import_job(self):
        os.makedirs(os.path.join(self.seed, 'POLIMI-NUIG-C4'))
        with open(os.path.join(self.seed, 'POLIMI-NUIG-C4', 'import.sh'), 'w') as f:
            f.write('#!/bin/bash\n$RMGpy/importChemkin.py --species POLIMI-NUIG-C4_gas.inp\n')
        run('add', '.', cwd=self.seed)
        run('commit', '-qm', 'Added POLIMI NUIG C4 mechanisms', cwd=self.seed)
        run('push', '-q', 'origin', 'master', cwd=self.seed)

        result = read_copy_sync.sync('webhook')
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(result['new_models'], ['POLIMI-NUIG-C4'])
        self.assertIn('Added 1 new model to the import jobs: POLIMI-NUIG-C4.', result['message'])
        job = ClusterJob.objects.get(name='POLIMI-NUIG-C4')
        self.assertEqual(job.status, ImportJobStatus.IDLE)
        self.assertEqual(read_copy_sync.sync()['new_models'], [])  # once

    def test_a_model_already_in_the_read_copy_gets_its_job_on_the_next_check(self):
        os.makedirs(os.path.join(self.read, 'Copied-by-hand'))
        open(os.path.join(self.read, 'Copied-by-hand', 'import.sh'), 'w').close()
        self.assertEqual(read_copy_sync.sync()['new_models'], ['Copied-by-hand'])
