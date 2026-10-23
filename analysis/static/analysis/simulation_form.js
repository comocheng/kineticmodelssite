/**
 * simulation_form.js
 *
 * Client-side logic for the "Run New Simulation" form.
 * - Loads kinetic models via AJAX with search
 * - Loads datasets via AJAX with fuel/type/apparatus/target filters
 * - Handles select-all / clear-all for dataset checkboxes
 * - Applies preselected model/dataset IDs from query params
 * - Updates counters
 */

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    // -----------------------------------------------------------------------
    // DOM references
    // -----------------------------------------------------------------------
    const form = document.getElementById('simulation-form');
    const modelSearch = document.getElementById('model-search');
    const modelList = document.getElementById('model-list');
    const modelCountEl = document.getElementById('model-count');
    const datasetSearch = document.getElementById('dataset-search');
    const datasetList = document.getElementById('dataset-list');
    const datasetCountEl = document.getElementById('dataset-count');
    const selectedCountEl = document.getElementById('selected-count');
    const datasetStatus = document.getElementById('dataset-status');
    const expTypeFilter = document.getElementById('exp-type-filter');
    const apparatusFilter = document.getElementById('apparatus-filter');
    const targetFilter = document.getElementById('target-filter');
    const selectAllBtn = document.getElementById('select-all');
    const clearAllBtn = document.getElementById('clear-all');
    const submitBtn = document.getElementById('submit-btn');

    // API URLs (from data attributes)
    const modelsApiUrl = modelList ? modelList.dataset.apiUrl : '';
    const modelCountsUrl = modelList ? modelList.dataset.countsUrl : '';
    const datasetsApiUrl = datasetList ? datasetList.dataset.apiUrl : '';

    // Pre-selections from server
    const preselectedDatasets = new Set(
        JSON.parse(form ? form.dataset.preselectedDatasets || '[]' : '[]')
            .map(String)
    );
    const preselectedModelId = form ? (form.dataset.preselectedModel || '') : '';

    // State
    let selectedModelId = preselectedModelId;
    let debounceTimerModels = null;
    let debounceTimerDatasets = null;

    // -----------------------------------------------------------------------
    // Utilities
    // -----------------------------------------------------------------------
    function debounce(fn, delay) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // -----------------------------------------------------------------------
    // Models
    // -----------------------------------------------------------------------
    function loadModels(keyword) {
        if (!modelList || !modelsApiUrl) return;

        const url = new URL(modelsApiUrl, window.location.origin);
        if (keyword) url.searchParams.set('q', keyword);

        modelList.innerHTML = '<div class="p-3 text-muted text-center"><i class="bi bi-hourglass-split me-1"></i>Loading…</div>';

        fetch(url)
            .then(r => r.json())
            .then(data => {
                const models = data.models || [];
                if (modelCountEl) modelCountEl.textContent = models.length;

                if (models.length === 0) {
                    modelList.innerHTML = '<div class="p-3 text-muted text-center">No models found.</div>';
                    return;
                }

                // Render radio buttons
                let html = '';
                models.forEach(m => {
                    const checked = String(m.id) === String(selectedModelId) ? 'checked' : '';
                    html += `
                        <label class="d-flex align-items-center px-3 py-2 border-bottom model-option ${checked ? 'bg-primary-subtle' : ''}" 
                               style="cursor:pointer;" data-model-id="${m.id}">
                            <input type="radio" name="kinetic_model" value="${m.id}" 
                                   class="form-check-input me-2 model-radio" ${checked}>
                            <span class="flex-grow-1">
                                <span class="fw-medium">${escapeHtml(m.model_name)}</span>
                                ${m.prime_id ? '<small class="text-muted ms-1">(' + escapeHtml(m.prime_id) + ')</small>' : ''}
                            </span>
                            <span class="model-counts text-muted small" data-model-id="${m.id}"></span>
                        </label>`;
                });
                modelList.innerHTML = html;

                // Attach click handlers
                modelList.querySelectorAll('.model-radio').forEach(radio => {
                    radio.addEventListener('change', function () {
                        selectedModelId = this.value;
                        modelList.querySelectorAll('.model-option').forEach(el => {
                            el.classList.toggle('bg-primary-subtle',
                                el.dataset.modelId === selectedModelId);
                        });
                    });
                });

                // Lazy-load counts for visible models
                loadModelCounts(models.map(m => m.id));
            })
            .catch(() => {
                modelList.innerHTML = '<div class="p-3 text-danger text-center">Failed to load models.</div>';
            });
    }

    function loadModelCounts(ids) {
        if (!modelCountsUrl || !ids.length) return;

        // Fetch in batches of 50
        const batchSize = 50;
        for (let i = 0; i < ids.length; i += batchSize) {
            const batch = ids.slice(i, i + batchSize);
            const url = new URL(modelCountsUrl, window.location.origin);
            url.searchParams.set('ids', batch.join(','));

            fetch(url)
                .then(r => r.json())
                .then(data => {
                    const counts = data.counts || {};
                    Object.entries(counts).forEach(([id, info]) => {
                        const el = modelList.querySelector(`.model-counts[data-model-id="${id}"]`);
                        if (el) {
                            el.innerHTML = `
                                <span class="badge bg-light text-dark me-1" title="Species">${info.species_count || 0} sp</span>
                                <span class="badge bg-light text-dark" title="Reactions">${info.reaction_count || 0} rxn</span>`;
                        }
                    });
                })
                .catch(() => { /* counts are non-critical */ });
        }
    }

    // -----------------------------------------------------------------------
    // Datasets
    // -----------------------------------------------------------------------
    function loadDatasets() {
        if (!datasetList || !datasetsApiUrl) return;

        const url = new URL(datasetsApiUrl, window.location.origin);

        const keyword = (datasetSearch ? datasetSearch.value.trim() : '');
        const expType = (expTypeFilter ? expTypeFilter.value : '');
        const apparatus = (apparatusFilter ? apparatusFilter.value : '');
        const target = (targetFilter ? targetFilter.value : '');

        if (keyword) url.searchParams.set('q', keyword);
        if (expType) url.searchParams.set('experiment_type', expType);
        if (apparatus) url.searchParams.set('apparatus_kind', apparatus);
        if (target) url.searchParams.set('target', target);

        datasetList.innerHTML = '<div class="p-3 text-muted text-center"><i class="bi bi-hourglass-split me-1"></i>Loading…</div>';

        fetch(url)
            .then(r => r.json())
            .then(data => {
                const datasets = data.datasets || [];
                if (datasetCountEl) datasetCountEl.textContent = datasets.length;

                if (datasets.length === 0) {
                    datasetList.innerHTML = '<div class="p-3 text-muted text-center">No datasets match the filters.</div>';
                    updateSelectedCount();
                    return;
                }

                let html = '';
                datasets.forEach(ds => {
                    const dsId = String(ds.id);
                    const checked = preselectedDatasets.has(dsId) ? 'checked' : '';

                    // Experiment type badge
                    let typeBadge = '';
                    if (ds.experiment_type === 'ignition delay') {
                        typeBadge = '<span class="badge bg-danger-subtle text-danger me-1">IDT</span>';
                    } else if (ds.experiment_type === 'laminar flame speed') {
                        typeBadge = '<span class="badge bg-warning-subtle text-warning me-1">LFS</span>';
                    } else if (ds.experiment_type === 'speciation') {
                        typeBadge = '<span class="badge bg-info-subtle text-info me-1">SR</span>';
                    }

                    // Fuel species pills
                    let fuelPills = '';
                    if (ds.fuel_species && ds.fuel_species.length > 0) {
                        fuelPills = ds.fuel_species.map(f =>
                            `<span class="badge bg-secondary-subtle text-secondary me-1">${escapeHtml(f)}</span>`
                        ).join('');
                    }

                    html += `
                        <label class="d-flex align-items-center px-3 py-2 border-bottom dataset-option"
                               style="cursor:pointer;" data-ds-id="${dsId}">
                            <input type="checkbox" name="datasets" value="${dsId}"
                                   class="form-check-input me-2 dataset-cb" ${checked}>
                            <span class="flex-grow-1">
                                <span class="fw-medium small">${escapeHtml(ds.short_name)}</span>
                                <span class="ms-1">${typeBadge}${fuelPills}</span>
                                ${ds.apparatus_kind ? '<small class="text-muted ms-1">' + escapeHtml(ds.apparatus_kind) + '</small>' : ''}
                            </span>
                            <span class="text-muted small">${ds.datapoints_count || 0} pts</span>
                        </label>`;
                });
                datasetList.innerHTML = html;

                // Checkbox highlighting
                datasetList.querySelectorAll('.dataset-cb').forEach(cb => {
                    cb.addEventListener('change', function () {
                        this.closest('.dataset-option').classList.toggle('bg-success-subtle', this.checked);
                        updateSelectedCount();
                    });
                    // Initial highlight for preselected
                    if (cb.checked) {
                        cb.closest('.dataset-option').classList.add('bg-success-subtle');
                    }
                });

                updateSelectedCount();
            })
            .catch(() => {
                datasetList.innerHTML = '<div class="p-3 text-danger text-center">Failed to load datasets.</div>';
            });
    }

    function updateSelectedCount() {
        const count = datasetList ? datasetList.querySelectorAll('.dataset-cb:checked').length : 0;
        if (selectedCountEl) selectedCountEl.textContent = count;
        // Disable submit if nothing selected
        if (submitBtn) {
            submitBtn.disabled = count === 0;
        }
    }

    // -----------------------------------------------------------------------
    // Event handlers
    // -----------------------------------------------------------------------

    // Model search (debounced)
    if (modelSearch) {
        modelSearch.addEventListener('input', debounce(function () {
            loadModels(this.value.trim());
        }, 300));
    }

    // Dataset search (debounced)
    if (datasetSearch) {
        datasetSearch.addEventListener('input', debounce(function () {
            loadDatasets();
        }, 300));
    }

    // Filter dropdowns → reload datasets
    [expTypeFilter, apparatusFilter, targetFilter].forEach(el => {
        if (el) el.addEventListener('change', loadDatasets);
    });

    // Select All / Clear All
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function () {
            if (!datasetList) return;
            datasetList.querySelectorAll('.dataset-cb').forEach(cb => {
                cb.checked = true;
                cb.closest('.dataset-option').classList.add('bg-success-subtle');
            });
            updateSelectedCount();
        });
    }
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', function () {
            if (!datasetList) return;
            datasetList.querySelectorAll('.dataset-cb').forEach(cb => {
                cb.checked = false;
                cb.closest('.dataset-option').classList.remove('bg-success-subtle');
            });
            updateSelectedCount();
        });
    }

    // Submit button label change based on auto_execute
    const autoExecCheckbox = document.getElementById('auto_execute');
    if (autoExecCheckbox && submitBtn) {
        autoExecCheckbox.addEventListener('change', function () {
            if (this.checked) {
                submitBtn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Run Simulation';
            } else {
                submitBtn.innerHTML = '<i class="bi bi-arrow-left-right me-1"></i>Review Mapping & Run';
            }
        });
    }

    // -----------------------------------------------------------------------
    // Initial load
    // -----------------------------------------------------------------------
    loadModels('');
    loadDatasets();
});
