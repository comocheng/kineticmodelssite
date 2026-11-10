"""Adapter that wraps a ChemKED dict (from batch_convert.convert_file) so it
can be used wherever a ReSpecThV2Data object is expected.

This allows the views.py helper methods (_generate_readable_name,
_extract_fuel_species, _get_apparatus_abbreviation, preview builder)
to work unchanged with data coming from either source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

VALUE_UNIT_RE = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(.*)$")


def _parse_chemked_value(raw):
    """Parse a ChemKED value entry like ['700 K'] or ['1.5 atm', {unc dict}].

    Returns (numeric_value, units, unc_dict_or_None).
    """
    if raw is None:
        return None, '', None
    if isinstance(raw, list):
        if not raw:
            return None, '', None
        first = raw[0]
        if isinstance(first, (int, float)):
            val, units = float(first), ''
        elif isinstance(first, str):
            m = VALUE_UNIT_RE.match(first)
            if m:
                val, units = float(m.group(1)), m.group(2).strip()
            else:
                return None, '', None
        else:
            return None, '', None
        unc = raw[1] if len(raw) > 1 and isinstance(raw[1], dict) else None
        return val, units, unc
    if isinstance(raw, (int, float)):
        return float(raw), '', None
    if isinstance(raw, str):
        m = VALUE_UNIT_RE.match(raw)
        if m:
            return float(m.group(1)), m.group(2).strip(), None
    return None, '', None


# ---------------------------------------------------------------------------
# Lightweight wrapper objects that mimic ReSpecThV2Data attribute access
# ---------------------------------------------------------------------------

@dataclass
class _Author:
    name: str = ''
    orcid: str = ''


@dataclass
class _Reference:
    doi: str = ''
    journal: str = ''
    volume: str = ''
    pages: str = ''
    year: Optional[int] = None
    title: str = ''
    number: str = ''
    publication_type: str = ''
    location: str = ''
    table: str = ''
    figure: str = ''
    description: str = ''
    authors: List[_Author] = field(default_factory=list)


@dataclass
class _Reaction:
    preferred_key: str = ''
    order: Optional[int] = None
    bulk_gas: str = ''
    reactants: List[str] = field(default_factory=list)
    products: List[str] = field(default_factory=list)


@dataclass
class _Apparatus:
    kind: str = ''
    mode: List[str] = field(default_factory=list)
    institution: str = ''
    facility: str = ''


@dataclass
class _CompositionComponent:
    species_name: str = ''
    amount: float = 0.0
    amount_units: str = 'mole fraction'
    inchi: str = ''
    smiles: str = ''
    cas: str = ''


@dataclass
class _CommonProperty:
    name: str = ''
    value: Any = None
    units: str = ''
    source_type: str = ''
    label: str = ''
    reference: str = ''
    kind: str = ''


@dataclass
class _Uncertainty:
    value: float = 0.0
    reference: str = ''
    units: str = ''
    kind: str = 'absolute'
    bound: str = 'plusminus'
    source_type: str = ''
    label: str = ''
    species_name: Optional[str] = None


@dataclass
class _EvaluatedStandardDeviation:
    species_name: str = ''
    value: float = 0.0
    units: str = 'mole fraction'
    kind: str = 'absolute'
    method: str = ''
    source_type: str = ''


@dataclass
class _Species:
    preferred_key: str = ''
    cas: str = ''
    inchi: str = ''
    smiles: str = ''
    chem_name: str = ''


@dataclass
class _DataProperty:
    name: str = ''
    id: str = ''
    label: str = ''
    source_type: str = ''
    units: str = ''
    reference: str = ''
    kind: str = ''
    bound: str = ''
    species_link: Optional[_Species] = None


@dataclass
class _DataPoint:
    values: Dict[str, Any] = field(default_factory=dict)


class ChemKEDDictAdapter:
    """Wraps a ChemKED dict to provide ReSpecThV2Data-compatible attribute access.

    This lets ``_generate_readable_name``, ``_extract_fuel_species``, the
    preview builder, and the import methods work with data from
    ``batch_convert.convert_file()`` without any code changes.
    """

    def __init__(self, d: Dict[str, Any]):
        self._d = d

    # -- Scalar metadata ------------------------------------------------

    @property
    def file_type(self):
        return self._d.get('file-type', 'experiment')

    @property
    def file_author(self):
        authors = self._d.get('file-authors') or []
        if authors:
            return authors[0].get('name', '')
        return ''

    @property
    def file_doi(self):
        return self._d.get('file-doi', '')

    @property
    def file_version(self):
        return str(self._d.get('file-version', '0'))

    @property
    def respecth_version(self):
        return self._d.get('respecth-version', '')

    @property
    def first_publication_date(self):
        return self._d.get('first-publication-date', '')

    @property
    def last_modification_date(self):
        return self._d.get('last-modification-date', '')

    @property
    def method(self):
        return self._d.get('method', '')

    @property
    def experiment_type(self):
        return self._d.get('experiment-type', '')

    @property
    def apparatus_kind(self):
        app = self._d.get('apparatus') or {}
        if isinstance(app, dict):
            return app.get('kind', '')
        return ''

    @property
    def comments(self):
        return self._d.get('comments') or []

    # -- Apparatus -------------------------------------------------------

    @property
    def apparatus(self):
        app = self._d.get('apparatus')
        if not app:
            return None
        raw_mode = app.get('mode', [])
        if isinstance(raw_mode, str):
            raw_mode = [raw_mode] if raw_mode else []
        return _Apparatus(
            kind=app.get('kind', ''),
            mode=raw_mode,
            institution=app.get('institution', ''),
            facility=app.get('facility', ''),
        )

    # -- Reference -------------------------------------------------------

    @property
    def reference(self):
        ref = self._d.get('reference')
        if not ref:
            return None
        authors = [_Author(name=a.get('name', ''), orcid=a.get('ORCID', ''))
                    for a in ref.get('authors', [])]
        year = ref.get('year')
        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None
        return _Reference(
            doi=ref.get('doi', ''),
            journal=ref.get('journal', ''),
            volume=str(ref.get('volume', '')),
            pages=ref.get('pages', ''),
            year=year,
            title=ref.get('title', ''),
            number=ref.get('number', ''),
            publication_type=ref.get('publication-type', ''),
            location=ref.get('location', ''),
            table=ref.get('table', ''),
            figure=ref.get('figure', ''),
            description=ref.get('detail', ''),
            authors=authors,
        )

    # -- Reactions -------------------------------------------------------

    @property
    def reactions(self):
        rxns = self._d.get('reactions') or []
        result = []
        for r in rxns:
            order = r.get('order')
            if order is not None:
                try:
                    order = int(order)
                except (ValueError, TypeError):
                    order = None
            result.append(_Reaction(
                preferred_key=r.get('preferred-key', ''),
                order=order,
                bulk_gas=r.get('bulk-gas', ''),
                reactants=r.get('reactants', []),
                products=r.get('products', []),
            ))
        return result

    @property
    def reaction(self):
        """Return first reaction (for _generate_readable_name compat)."""
        rxns = self.reactions
        return rxns[0] if rxns else None

    # -- Initial composition ---------------------------------------------

    @property
    def initial_composition(self):
        common = self._d.get('common-properties') or {}
        comp = common.get('composition')
        if not comp:
            return []
        return self._parse_composition_block(comp)

    def _parse_composition_block(self, comp: Dict[str, Any]):
        species_list = comp.get('species') or []
        kind = comp.get('kind', 'mole fraction')
        result = []
        for sp in species_list:
            amount_raw = sp.get('amount') or []
            if isinstance(amount_raw, list) and amount_raw:
                amount = float(amount_raw[0])
            elif isinstance(amount_raw, (int, float)):
                amount = float(amount_raw)
            else:
                amount = 0.0
            result.append(_CompositionComponent(
                species_name=sp.get('species-name', ''),
                amount=amount,
                amount_units=kind,
                inchi=sp.get('InChI', ''),
                smiles=sp.get('SMILES', ''),
                cas=sp.get('CAS', ''),
            ))
        return result

    # -- Common properties ------------------------------------------------

    @property
    def common_properties(self):
        common = self._d.get('common-properties') or {}
        result = []
        for key, val in common.items():
            if key in ('composition', 'ignition-type', '_pending_esd', '_pending_unc'):
                continue
            parsed_val, units, _unc = _parse_chemked_value(val)
            result.append(_CommonProperty(
                name=key.replace('-', ' '),
                value=parsed_val,
                units=units,
            ))
        return result

    # -- Uncertainties (from common-properties inline uncertainty dicts) --

    @property
    def uncertainties(self):
        """Extract global uncertainties from common-properties inline dicts."""
        common = self._d.get('common-properties') or {}
        result = []
        for key, val in common.items():
            if key in ('composition', 'ignition-type', '_pending_esd', '_pending_unc'):
                continue
            if isinstance(val, list) and len(val) > 1 and isinstance(val[1], dict):
                unc_dict = val[1]
                ref_name = key.replace('-', ' ')
                unc_type = unc_dict.get('uncertainty-type', 'absolute')
                sourcetype = unc_dict.get('uncertainty-sourcetype', '')

                sym = unc_dict.get('uncertainty')
                upper = unc_dict.get('upper-uncertainty')
                lower = unc_dict.get('lower-uncertainty')

                def _extract_numeric(v):
                    if v is None:
                        return None
                    if isinstance(v, (int, float)):
                        return float(v)
                    if isinstance(v, str):
                        m = VALUE_UNIT_RE.match(v)
                        return float(m.group(1)) if m else None
                    return None

                if sym is not None:
                    result.append(_Uncertainty(
                        value=_extract_numeric(sym) or 0.0,
                        reference=ref_name,
                        kind=unc_type,
                        bound='plusminus',
                        source_type=sourcetype,
                    ))
                if upper is not None:
                    result.append(_Uncertainty(
                        value=_extract_numeric(upper) or 0.0,
                        reference=ref_name,
                        kind=unc_type,
                        bound='plus',
                        source_type=sourcetype,
                    ))
                if lower is not None:
                    result.append(_Uncertainty(
                        value=_extract_numeric(lower) or 0.0,
                        reference=ref_name,
                        kind=unc_type,
                        bound='minus',
                        source_type=sourcetype,
                    ))
        # Per-species uncertainties from composition
        comp = common.get('composition')
        if comp:
            for sp in comp.get('species', []):
                amount_list = sp.get('amount') or []
                if isinstance(amount_list, list) and len(amount_list) > 1 and isinstance(amount_list[1], dict):
                    meta = amount_list[1]
                    unc_type = meta.get('uncertainty-type', '')
                    sourcetype = meta.get('uncertainty-sourcetype', '')
                    sym = meta.get('uncertainty')
                    upper = meta.get('upper-uncertainty')
                    lower = meta.get('lower-uncertainty')
                    sp_name = sp.get('species-name', '')

                    def _extract_numeric_sp(v):
                        if v is None:
                            return None
                        if isinstance(v, (int, float)):
                            return float(v)
                        if isinstance(v, str):
                            m = VALUE_UNIT_RE.match(v)
                            return float(m.group(1)) if m else None
                        return None

                    if sym is not None:
                        result.append(_Uncertainty(
                            value=_extract_numeric_sp(sym) or 0.0,
                            reference='composition',
                            kind=unc_type,
                            bound='plusminus',
                            source_type=sourcetype,
                            species_name=sp_name,
                        ))
                    if upper is not None:
                        result.append(_Uncertainty(
                            value=_extract_numeric_sp(upper) or 0.0,
                            reference='composition',
                            kind=unc_type,
                            bound='plus',
                            source_type=sourcetype,
                            species_name=sp_name,
                        ))
                    if lower is not None:
                        result.append(_Uncertainty(
                            value=_extract_numeric_sp(lower) or 0.0,
                            reference='composition',
                            kind=unc_type,
                            bound='minus',
                            source_type=sourcetype,
                            species_name=sp_name,
                        ))
        # Per-species uncertainties from _pending_unc (measured species not in initial composition)
        for entry in common.get('_pending_unc', []):
            result.append(_Uncertainty(
                value=float(entry.get('value', 0)),
                reference='composition',
                kind=entry.get('kind', 'absolute'),
                bound=entry.get('bound', 'plusminus'),
                source_type=entry.get('sourcetype', ''),
                species_name=entry.get('species-name', ''),
            ))
        # Check first datapoint's measured-composition for inline uncertainties
        # (inlined during convert_file post-processing from _pending_unc)
        seen_species = {u.species_name for u in result if u.species_name}
        dps = self._d.get('datapoints') or []
        if dps:
            mc = dps[0].get('measured-composition')
            if mc:
                for sp in mc.get('species', []):
                    sp_name = sp.get('species-name', '')
                    if sp_name in seen_species:
                        continue
                    amount_list = sp.get('amount') or []
                    if isinstance(amount_list, list) and len(amount_list) > 1 and isinstance(amount_list[1], dict):
                        meta = amount_list[1]
                        unc_type = meta.get('uncertainty-type', '')
                        sourcetype = meta.get('uncertainty-sourcetype', '')
                        sym = meta.get('uncertainty')
                        upper = meta.get('upper-uncertainty')
                        lower = meta.get('lower-uncertainty')
                        if sym is not None:
                            result.append(_Uncertainty(
                                value=float(sym) if isinstance(sym, (int, float)) else 0.0,
                                reference='composition',
                                kind=unc_type,
                                bound='plusminus',
                                source_type=sourcetype,
                                species_name=sp_name,
                            ))
                        if upper is not None:
                            result.append(_Uncertainty(
                                value=float(upper) if isinstance(upper, (int, float)) else 0.0,
                                reference='composition',
                                kind=unc_type,
                                bound='plus',
                                source_type=sourcetype,
                                species_name=sp_name,
                            ))
                        if lower is not None:
                            result.append(_Uncertainty(
                                value=float(lower) if isinstance(lower, (int, float)) else 0.0,
                                reference='composition',
                                kind=unc_type,
                                bound='minus',
                                source_type=sourcetype,
                                species_name=sp_name,
                            ))
        return result

    # -- Evaluated standard deviations -----------------------------------

    @property
    def evaluated_standard_deviations(self):
        common = self._d.get('common-properties') or {}
        result = []
        # Check composition species for inline ESD
        comp = common.get('composition')
        if comp:
            for sp in comp.get('species', []):
                amount_list = sp.get('amount') or []
                if isinstance(amount_list, list) and len(amount_list) > 1 and isinstance(amount_list[1], dict):
                    meta = amount_list[1]
                    esd = meta.get('evaluated-standard-deviation')
                    if esd is not None:
                        result.append(_EvaluatedStandardDeviation(
                            species_name=sp.get('species-name', ''),
                            value=float(esd) if isinstance(esd, (int, float)) else 0.0,
                            kind=meta.get('evaluated-standard-deviation-type', 'absolute'),
                            method=meta.get('evaluated-standard-deviation-method', ''),
                            source_type=meta.get('evaluated-standard-deviation-sourcetype', ''),
                        ))
        # Also check scalar properties for inline ESD
        for key, val in common.items():
            if key in ('composition', 'ignition-type', '_pending_esd', '_pending_unc'):
                continue
            if isinstance(val, list) and len(val) > 1 and isinstance(val[1], dict):
                meta = val[1]
                esd = meta.get('evaluated-standard-deviation')
                if esd is not None:
                    result.append(_EvaluatedStandardDeviation(
                        species_name='',
                        value=float(esd) if isinstance(esd, (int, float)) else 0.0,
                        kind=meta.get('evaluated-standard-deviation-type', 'absolute'),
                        method=meta.get('evaluated-standard-deviation-method', ''),
                        source_type=meta.get('evaluated-standard-deviation-sourcetype', ''),
                    ))
        # Entries from _pending_esd (measured species not in initial composition)
        for entry in common.get('_pending_esd', []):
            result.append(_EvaluatedStandardDeviation(
                species_name=entry.get('species-name', ''),
                value=float(entry.get('value', 0)),
                units=entry.get('units', 'mole fraction'),
                kind=entry.get('kind', 'absolute'),
                method=entry.get('method', ''),
                source_type=entry.get('sourcetype', ''),
            ))
        # Check first datapoint's measured-composition for inline ESDs
        # (these are inlined during convert_file post-processing)
        seen_species = {e.species_name for e in result}
        dps = self._d.get('datapoints') or []
        if dps:
            mc = dps[0].get('measured-composition')
            if mc:
                for sp in mc.get('species', []):
                    sp_name = sp.get('species-name', '')
                    if sp_name in seen_species:
                        continue
                    amount_list = sp.get('amount') or []
                    if isinstance(amount_list, list) and len(amount_list) > 1 and isinstance(amount_list[1], dict):
                        meta = amount_list[1]
                        esd = meta.get('evaluated-standard-deviation')
                        if esd is not None:
                            result.append(_EvaluatedStandardDeviation(
                                species_name=sp_name,
                                value=float(esd) if isinstance(esd, (int, float)) else 0.0,
                                kind=meta.get('evaluated-standard-deviation-type', 'absolute'),
                                method=meta.get('evaluated-standard-deviation-method', ''),
                                source_type=meta.get('evaluated-standard-deviation-sourcetype', ''),
                            ))
        return result

    # -- DataGroup properties + datapoints --------------------------------

    @property
    def data_properties(self):
        """Synthesize DataProperty objects from datapoint keys.

        Since the ChemKED dict flattens property definitions into the
        datapoints themselves, we reconstruct property-like objects using
        synthetic IDs so the importer can iterate them.
        """
        dps = self._d.get('datapoints') or []
        if not dps:
            return []
        # Gather all keys that appear across datapoints
        keys = {}
        for dp in dps:
            for k in dp:
                if k not in keys:
                    keys[k] = dp[k]
        props = []
        for i, (k, sample_val) in enumerate(keys.items()):
            pid = f'x{i+1}'
            val, units, _unc = _parse_chemked_value(sample_val)
            props.append(_DataProperty(
                name=k.replace('-', ' '),
                id=pid,
                units=units,
            ))
        return props

    @property
    def datapoints(self):
        """Convert datapoints from ChemKED dict format to _DataPoint objects.

        Each datapoint maps synthetic property IDs to their raw values.
        """
        dps = self._d.get('datapoints') or []
        if not dps:
            return []

        # Build key→pid mapping from data_properties
        all_keys = []
        for dp in dps:
            for k in dp:
                if k not in all_keys:
                    all_keys.append(k)
        key_to_pid = {k: f'x{i+1}' for i, k in enumerate(all_keys)}

        result = []
        for dp in dps:
            values = {}
            for k, raw in dp.items():
                pid = key_to_pid.get(k, k)
                val, _units, _unc = _parse_chemked_value(raw)
                if val is not None:
                    values[pid] = val
            result.append(_DataPoint(values=values))
        return result

    # -- Raw dict access -------------------------------------------------

    @property
    def raw(self):
        """Direct access to the underlying ChemKED dict."""
        return self._d
