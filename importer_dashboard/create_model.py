"""
Add a model through the Importer (the page /kineticmodel/create/).

The files go into a new draft (importer_dashboard/drafts.py) in the folder template of an import
job: mechanism.txt, thermo.txt, transport.txt, SMILES.txt, source.txt and import.sh. The files are
kept byte for byte under these names; their original names are written in source.txt, so the
original-mechanism download can give them back. import.sh is written here, without a port: the
port allocator gives each run a free one. Check files then reads the files as an import would, and
the job starts when it passes. Nothing goes into the database here: the model arrives there after
its pull request to RMG-models is merged (import_rmg_models).
"""

import logging
import re

from django import forms
from django.utils import timezone

from . import drafts, editor
from .models import ClusterJob, Draft, ImportJobConfig, ImportJobStatus, JobLog

logger = logging.getLogger(__name__)

DOI_PATTERN = re.compile(r'10\.\d{4,9}/[^\s"<>]+')
LIVE = (ImportJobStatus.RUNNING, ImportJobStatus.PENDING, ImportJobStatus.AWAITING_INPUT)


# The folder of a new model, as the create page lists it
FOLDER_FILES = [
    ('mechanism.txt', 'your mechanism file'),
    ('thermo.txt', 'your thermo file, unless the thermo is in the mechanism'),
    ('transport.txt', 'your transport file, if the model has one'),
    ('SMILES.txt', 'your SMILES.txt, or an empty one'),
    ('source.txt', 'the citation, the DOI, the download page and the original file names'),
    ('import.sh', 'written by Prometheus'),
]


def dois_in(text):
    """The DOIs in `text`, the way import_rmg_models finds the DOI of a source.txt."""
    found = set()
    for doi in DOI_PATTERN.findall(text or ''):
        doi = doi.rstrip('.,;')
        for opening, closing in ('()', '[]'):
            if doi.endswith(closing) and doi.count(closing) - doi.count(opening) == 1:
                doi = doi[:-1]
        found.add(doi)
    return found


class NewModelForm(forms.Form):
    # The widgets carry the classes of the kinetic model form (Figma 170:7072), whose styles the
    # create page shares (database/kineticmodel_form_styles.html)
    folder = forms.CharField(
        max_length=200,
        label='Folder in RMG-models',
        help_text='A name, or Journal/NNN-Author as in RMG-models.',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'e.g. PCI2019/555-Sun',
                'autocomplete': 'off',
                'spellcheck': 'false',
            }
        ),
    )
    mechanism = forms.FileField(label='Mechanism file')
    thermo = forms.FileField(required=False, label='Thermo file')
    thermo_in_mechanism = forms.BooleanField(
        required=False,
        label='The thermo is in the mechanism file',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    transport = forms.FileField(required=False, label='Transport file')
    smiles = forms.FileField(required=False, label='SMILES.txt')
    citation = forms.CharField(
        label='Citation',
        help_text='Authors (year). Title. Journal, volume, pages.',
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'e.g. Y. Li, H. J. Curran (2017). The oxidation of 2-butene. '
                'Proc. Combust. Inst. 36, 403-411.',
            }
        ),
    )
    doi = forms.CharField(
        required=False,
        label='DOI',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 10.1016/j.proci.2016.05.052',
                'spellcheck': 'false',
            }
        ),
    )
    url = forms.URLField(
        required=False,
        label='Downloaded from',
        help_text=(
            "Only if the files are not the paper's supplementary material, "
            "e.g. the group's mechanism page."
        ),
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
    )
    start = forms.BooleanField(
        required=False,
        initial=True,
        label='Start the import when the files pass Check files',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean_folder(self):
        folder = self.cleaned_data['folder'].strip().strip('/')
        if not drafts.valid_model_folder(folder):
            raise forms.ValidationError(
                'Use letters, digits and . _ - ( ) + , only, as a name or Journal/NNN-Author.'
            )
        draft = Draft.objects.filter(model_folder=folder, status='open').first()
        if draft:
            raise forms.ValidationError(f'{folder} already has an open draft ({draft.branch}).')
        job = ClusterJob.objects.filter(name=folder).first()
        if job and job.status in LIVE:
            raise forms.ValidationError(
                f'An import job of {folder} is {job.get_status_display().lower()}.'
            )
        return folder

    def clean_doi(self):
        doi = self.cleaned_data['doi'].strip()
        doi = re.sub(r'^(https?://(dx\.)?doi\.org/|doi:\s*)', '', doi, flags=re.I)
        if doi and not DOI_PATTERN.fullmatch(doi):
            raise forms.ValidationError('This is not a DOI (10.<number>/<name>).')
        return doi

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('thermo') and not cleaned.get('thermo_in_mechanism'):
            self.add_error(
                'thermo', 'Upload the thermo file, or say that the thermo is in the mechanism file.'
            )
        for name in ('mechanism', 'thermo', 'transport', 'smiles'):
            upload = cleaned.get(name)
            if upload and upload.size > editor.MAX_UPLOAD_BYTES:
                self.add_error(name, f'Larger than {editor.MAX_UPLOAD_BYTES // 2**20} MB.')
        found = set()
        for name in ('citation', 'doi', 'url'):
            found |= dois_in(cleaned.get(name, ''))
        if len(found) > 1:
            self.add_error(
                'doi',
                'source.txt can name one DOI only (the database looks the paper up by it). '
                f'Found: {", ".join(sorted(found))}.',
            )
        return cleaned


def import_sh(thermo_name, transport_name=None):
    """The import.sh of a new model: no port (each run gets a free one) and no SBATCH lines."""
    lines = ['#!/bin/bash', '# Written by Prometheus. The Importer gives each run a free port.']
    if transport_name:
        lines.append(f'# transport: {transport_name}')
    lines += [
        'python $RMGpy/importChemkin.py \\',
        '\t--species mechanism.txt \\',
        '\t--reactions mechanism.txt \\',
        f'\t--thermo {thermo_name} \\',
        '\t--known SMILES.txt',
        '',
    ]
    return '\n'.join(lines)


def source_txt(cleaned, original_names, user):
    lines = [cleaned['citation'].strip().replace('\r\n', '\n')]
    if cleaned.get('doi'):
        lines.append(f"DOI: https://doi.org/{cleaned['doi']}")
    if cleaned.get('url'):
        lines.append(f"Downloaded from {cleaned['url']}")
    lines.append(
        'Original files: '
        + '; '.join(f'{ours} = {theirs}' for ours, theirs in original_names.items())
    )
    who = (user.get_full_name() or user.username) if user else 'Prometheus'
    lines.append(f'Added on Prometheus by {who} on {timezone.now():%Y-%m-%d}.')
    return '\n'.join(lines) + '\n'


def create(cleaned, user):
    """
    Make the draft of a new model with its files, and its import job. Returns (job, draft,
    warning). The first commit holds the files as uploaded.
    """
    folder = cleaned['folder']
    draft, warning = drafts.open_draft(folder, user=user, is_new_model=True)
    try:
        files = {'mechanism.txt': cleaned['mechanism'].read()}
        original = {'mechanism.txt': cleaned['mechanism'].name}
        thermo_name = 'mechanism.txt'
        if cleaned.get('thermo'):
            files['thermo.txt'] = cleaned['thermo'].read()
            original['thermo.txt'] = cleaned['thermo'].name
            thermo_name = 'thermo.txt'
        transport_name = None
        if cleaned.get('transport'):
            files['transport.txt'] = cleaned['transport'].read()
            original['transport.txt'] = cleaned['transport'].name
            transport_name = 'transport.txt'
        if cleaned.get('smiles'):
            files['SMILES.txt'] = cleaned['smiles'].read()
            original['SMILES.txt'] = cleaned['smiles'].name
        else:
            files['SMILES.txt'] = b''
        files['source.txt'] = source_txt(cleaned, original, user).encode('utf-8')
        files['import.sh'] = import_sh(thermo_name, transport_name).encode('utf-8')
        editor.save(draft, files, 'add the model files as uploaded', user)
    except Exception:
        drafts.close_draft(draft, drafts.DraftStatus.DISCARDED)
        raise

    config = ImportJobConfig.objects.filter(is_default=True).first()
    job, _ = ClusterJob.objects.get_or_create(
        name=folder, defaults={'status': ImportJobStatus.IDLE, 'config': config}
    )
    ClusterJob.objects.filter(pk=job.pk).update(draft=draft)
    job.draft = draft
    JobLog.objects.create(
        job=job,
        log_type='info',
        message=(
            f'Model added by {user.username} in draft {draft.branch}: ' + ', '.join(sorted(files))
        ),
    )
    if cleaned.get('start'):
        Draft.objects.filter(pk=draft.pk).update(start_job_after_check=True)
        draft.start_job_after_check = True
        editor.start_check(draft)
    return job, draft, warning


def start_checked_job(job, manager):
    """
    Start the job of a draft that waits for Check files (the create page), once the check has
    ended: 'started', 'failed' (the check failed; the job does not start), or None (nothing yet).
    """
    draft = job.draft
    if draft is None or not draft.is_open or not draft.start_job_after_check:
        return None
    status = editor.check_status(draft)
    if status is None or status['state'] == 'running':
        return None
    if not Draft.objects.filter(pk=draft.pk, start_job_after_check=True).update(
        start_job_after_check=False
    ):
        return None  # someone else did it
    draft.start_job_after_check = False
    if status['state'] != 'passed':
        JobLog.objects.create(
            job=job,
            log_type='error',
            message=(
                'Check files failed, so the import did not start. '
                'Correct the files on the Files tab, '
                f"then check them again.\n{status.get('log', '')[-3000:]}"
            ),
        )
        return 'failed'
    if job.status in LIVE:
        return None
    ClusterJob.objects.filter(pk=job.pk).update(started_by=draft.created_by)
    job.started_by = draft.created_by
    try:
        task_id, _ = manager.start_job(job)
    except Exception as e:  # e.g. Celery's broker is down: say so on the job page, don't fail it
        logger.exception(f"Could not start {job.name} after Check files")
        JobLog.objects.create(
            job=job,
            log_type='error',
            message=(
                f'The files passed Check files, but the import could not start: {e}. '
                'Start it again.'
            ),
        )
        return 'failed'
    ClusterJob.objects.filter(pk=job.pk).update(celery_task_id=task_id)
    JobLog.objects.create(
        job=job, log_type='info', message='The files passed Check files; the import started.'
    )
    return 'started'
