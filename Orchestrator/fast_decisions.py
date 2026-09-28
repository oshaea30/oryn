"""Bounded routing proposals, never semantic facts or permission to spend.

No network adapters here. A future paid adapter must use a reviewed budget gateway;
implementing this protocol alone does not enable it in the application.
"""
from copy import deepcopy
import math
from typing import Protocol


CONTRACT = 'oryn-fast-decisions-v1'
POINTS = {
    'asset_route': {'actions': ['library', 'retrieval', 'generation'],
                    'state': 'active', 'purpose': 'Choose an eligible acquisition path.'},
    'geometry_triage': {'actions': ['investigate', 'preserve_unknown'],
                        'state': 'active', 'purpose': 'Prioritize pieces, without identifying or dropping them.'},
    'reference_triage': {'actions': ['accept_candidate', 'investigate', 'reject'],
                         'state': 'active', 'purpose': 'Filter object/revision metadata before evidence synthesis.'},
    'representation_route': {'actions': ['visual', 'explorable', 'technical', 'escalate'],
                             'state': 'planned', 'purpose': 'Interpret requested depth; never advertise unbuilt capabilities.'},
    'component_family': {'actions': ['candidate', 'preserve_unknown', 'escalate'],
                         'state': 'planned', 'purpose': 'Suggest a family, not a verified component identity.'},
    'evidence_sufficiency': {'actions': ['answer', 'search_more', 'preserve_unknown', 'escalate'],
                            'state': 'planned', 'purpose': 'Choose the next investigation step.'},
    'semantic_exposure': {'actions': ['geometric', 'candidate', 'reference_supported', 'escalate'],
                         'state': 'planned', 'purpose': 'Propose a level; deterministic manifest gates remain authoritative.'},
}


class FastDecisionProvider(Protocol):
    name: str
    version: str

    def decide(self, point: str, facts: list[dict]) -> list[dict]:
        """One {id, action, reason_code} per item; no tools or free-form actions."""
        ...


class LocalDecisionProvider:
    name = 'oryn-local-rules'
    version = '1'

    def decide(self, point, facts):
        output = []
        for item in facts:
            if point == 'asset_route':
                action, reason = ('library', 'exact_saved_match') if item['exact_saved_match'] else ('generation', 'no_exact_saved_match')
            elif point == 'geometry_triage':
                # Ordinal geometry ranking, NOT a probability or component label.
                chosen = item['priority_rank'] <= item['analysis_limit']
                action, reason = ('investigate', 'within_geometry_review_budget') if chosen else ('preserve_unknown', 'deferred_not_discarded')
            elif point == 'reference_triage':
                # Facts must be prepared by a retrieval adapter. These flags do NOT
                # establish authority, accuracy, licensing or reference support.
                if item.get('object_match') is False or item.get('revision_match') is False:
                    action, reason = 'reject', 'explicit_metadata_mismatch'
                elif item.get('object_match') is True and item.get('revision_match') is True:
                    action, reason = 'accept_candidate', 'metadata_matches_not_verified'
                else:
                    action, reason = 'investigate', 'metadata_unknown'
            else:
                raise ValueError('Decision point is not implemented by the local baseline.')
            output.append({'id': item['id'], 'action': action, 'reason_code': reason})
        return output


def validate_results(point, facts, output):
    """Reject the entire batch on omissions, extra IDs, duplicates or extra fields."""
    allowed = POINTS[point]['actions']
    ids = [item['id'] for item in facts]
    if len(set(ids)) != len(ids) or not isinstance(output, list) or len(output) != len(ids):
        raise ValueError('Invalid decision batch cardinality.')
    seen = set()
    for item in output:
        if (not isinstance(item, dict) or set(item) != {'id', 'action', 'reason_code'} or
                not isinstance(item['id'], str) or item['id'] not in ids or item['id'] in seen or
                item['action'] not in allowed or not isinstance(item['reason_code'], str) or
                not item['reason_code'] or len(item['reason_code']) > 80 or
                any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in item['reason_code'])):
            raise ValueError('Invalid structured decision.')
        seen.add(item['id'])
    return deepcopy(output)


def geometry_facts(manifest, limit=8):
    """Measure/rank existing bounds, preserving IDs. No shape-to-anatomy inference."""
    if type(limit) is not int or not 1 <= limit <= 32:
        raise ValueError('Invalid geometry review budget.')
    measured = []
    for piece in manifest['geometry_pieces']:
        size = (piece.get('bounds_local') or {}).get('size')
        if size is not None and (len(size) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in size)):
            raise ValueError('Invalid geometry measurement.')
        triangles = piece.get('triangles')
        if triangles is not None and (type(triangles) is not int or triangles < 0):
            raise ValueError('Invalid triangle count.')
        measured.append({'id': piece['id'], 'triangles': triangles, 'bounds_size_local': size,
                         'analysis_limit': limit})
    # Missing measurements first, then highest triangle count; stable ID tie-break.
    measured.sort(key=lambda item: (item['triangles'] is not None, -(item['triangles'] or 0), item['id']))
    for rank, item in enumerate(measured, 1):
        item['priority_rank'] = rank
    return measured
