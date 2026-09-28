"""Deterministic geometry ingestion. No semantic inference, provider or USB calls."""
import hashlib
import json
from pathlib import Path

from asset_inspection import inspect_glb
from mesh_islands import bounds, components, decode, separate
from providers import GenerationError

PIPELINE = 'oryn-ingestion-v1'
MAX_ACTIVE_PARTS = 64  # OrynAssembly.MaximumParts; NOT an object graph size limit.
STATES = {'unidentified', 'candidate', 'reference-supported', 'verified'}
FILES = {'geometry': 'model.glb', 'textured': 'textured.glb'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def capability(status, reason):
    return {'status': status, 'reason': reason}


def ingest(data, provenance):
    report = inspect_glb(data)
    if report['preflight'] != 'PASS':
        raise GenerationError('Ingestion requires passing static preflight.')
    source_hash = digest(data)
    source_doc = json.loads(data[20:20 + int.from_bytes(data[12:16], 'little')])
    transforms = [{'node_index': i, **{k: node[k] for k in ('matrix', 'translation', 'rotation', 'scale', 'children') if k in node}}
                  for i, node in enumerate(source_doc.get('nodes', []))]
    pieces, derived = [], None
    method, issue = 'mesh_nodes', ''
    evidence = [{'id': 'source-inspection', 'kind': 'measurement', 'source_sha256': source_hash,
                 'method': 'static_glb_inspection', 'triangles': report['triangles'], 'mesh_objects': report['mesh_objects']}]
    try:
        doc, positions, faces = decode(data)
    except GenerationError as error:
        # Preserve unsupported layouts unchanged; never discard attributes to split.
        issue = str(error)
        for node in report['hierarchy']:
            if node['mesh_index'] is not None:
                pieces.append({'id': source_hash + ':node:' + str(node['node_index']),
                    'kind': 'mesh_instance', 'source_node': node['node_index'],
                    'bounds_local': None, 'triangle_indices': None, 'semantic_status': 'unidentified'})
    else:
        method = 'vertex_index_connectivity'
        islands = components(positions, faces)
        evidence.append({'id': 'topology', 'kind': 'measurement', 'method': method,
            'index_islands': len(islands), 'exact_position_islands': len(components(positions, faces, True)),
            'note': 'Disconnected geometry is not proof of mechanical components. No cuts or tolerance welding.'})
        for number, face_ids in enumerate(islands, 1):
            used = sorted({v for i in face_ids for v in faces[i]})
            pieces.append({'id': source_hash + f':island:{number:03}', 'kind': 'disconnected_surface',
                'source_node': 0, 'coordinate_frame': 'source_node_local', 'bounds_local': bounds([positions[v] for v in used]),
                'triangle_indices': face_ids, 'triangles': len(face_ids), 'semantic_status': 'unidentified',
                'runtime_node': f'island_{number:03}' if 2 <= len(islands) <= MAX_ACTIVE_PARTS else None})
        if 2 <= len(islands) <= MAX_ACTIVE_PARTS:
            try:
                derived, _, _ = separate(data, root_name='ORYN / source transform')
            except GenerationError as error:
                issue = str(error)
        elif len(islands) > MAX_ACTIVE_PARTS:
            issue = f'{len(islands)} geometric pieces exceed the {MAX_ACTIVE_PARTS}-active-part runtime limit. All pieces retained; hierarchical interaction is not implemented yet.'
        else:
            issue = 'Only one connected geometric piece was detected.'
    # Native multi-node models remain untouched. No claim of mechanical identity.
    take_apart = derived is not None or (method == 'mesh_nodes' and 2 <= report['mesh_objects'] <= MAX_ACTIVE_PARTS)
    if take_apart:
        reason = f'{len(pieces)} geometric interaction targets prepared; component identities are unverified.'
    else:
        reason = issue or 'No supported multipart representation is available.'
    output = derived if derived is not None else data
    manifest = {
        'schema_version': 1, 'asset_id': source_hash, 'revision': 1, 'pipeline': PIPELINE,
        'source_geometry': {'sha256': source_hash, 'bytes': len(data), 'triangles': report['triangles'], 'mesh_objects': report['mesh_objects'], 'node_transforms': transforms},
        'geometry_pieces': pieces, 'components': [], 'component_mappings': [],
        'assembly_hierarchy': {'id': source_hash + ':root', 'kind': 'geometric_container',
            'component_ids': [], 'geometry_ids': [p['id'] for p in pieces], 'children': []},
        'evidence': evidence,
        'unresolved_mappings': [{'geometry_id': p['id'], 'status': 'unidentified', 'reason': 'No component identification has been performed.'} for p in pieces],
        'capabilities': {
            'whole_object_manipulation': capability('supported', 'Static model fits the existing whole-object import contract.'),
            'geometric_explosion': capability('supported' if take_apart else 'unsupported', reason),
            'geometric_isolation': capability('supported' if take_apart else 'unsupported', reason),
            'component_isolation': capability('unsupported', 'No identified component mappings.'),
            'semantic_explanation': capability('unsupported', 'No reference-backed component knowledge.'),
            'verified_internal_assembly': capability('unsupported', 'Internal completeness and mechanical correctness have not been established.')},
        'provenance': {k: provenance.get(k) for k in ('job_id', 'provider', 'profile', 'provider_task_id', 'reused_from')},
        'analysis': {'method': method, 'limitation': issue, 'semantic_inference_performed': False},
        'runtime': {'artifact': 'prepared' if derived is not None else 'source', 'sha256': digest(output),
            'active_part_budget': MAX_ACTIVE_PARTS, 'prepared_targets': len(pieces) if take_apart else 0,
            'validation': 'static_preflight_only', 'headset_verified': False},
    }
    validate_manifest(manifest, source_hash)
    return manifest, derived


def validate_manifest(manifest, source_hash):
    """Versioned structural checks; epistemic state never inferred from a score."""
    if manifest.get('schema_version') != 1 or manifest.get('pipeline') != PIPELINE or manifest.get('asset_id') != source_hash or manifest.get('source_geometry', {}).get('sha256') != source_hash:
        raise GenerationError('Ingestion manifest version or source binding mismatch; existing record preserved.')
    geometry = {p['id'] for p in manifest['geometry_pieces']}
    if len(geometry) != len(manifest['geometry_pieces']):
        raise GenerationError('Duplicate geometry IDs in ingestion manifest.')
    component_ids = {c['id'] for c in manifest['components']}
    evidence_ids = {e['id'] for e in manifest['evidence']}
    for mapping in manifest['component_mappings']:
        if (mapping.get('status') not in STATES or not set(mapping.get('geometry_ids', [])) <= geometry or
                not mapping.get('geometry_ids') or mapping.get('component_id') not in component_ids or
                not set(mapping.get('evidence', [])) <= evidence_ids or
                not mapping.get('derived_by', {}).get('method') or
                mapping.get('human_review', {}).get('status') not in {'not_reviewed', 'accepted', 'rejected'} or
                'confidence' in mapping):
            raise GenerationError('Invalid component mapping or missing provenance.')
        if mapping['status'] in {'reference-supported', 'verified'} and not mapping.get('evidence'):
            raise GenerationError('Supported/verified mappings require evidence.')
        if mapping['status'] == 'reference-supported' and not any(e['id'] in mapping['evidence'] and e.get('kind') == 'reference' and e.get('source') for e in manifest['evidence']):
            raise GenerationError('Reference-supported mapping requires an identified reference source.')
        if mapping['status'] == 'verified' and not mapping.get('verification', {}).get('method'):
            raise GenerationError('Verified mapping requires an explicit verification record.')
        if mapping['derived_by']['method'] == 'multimodal_model' and not all(mapping['derived_by'].get(k) for k in ('provider', 'model')):
            raise GenerationError('Model-derived mappings require provider and model provenance.')


def summary(manifest):
    return {'asset_id': manifest['asset_id'], 'revision': manifest['revision'],
        'piece_count': len(manifest['geometry_pieces']), 'component_count': len(manifest['components']),
        'capabilities': manifest['capabilities'], 'runtime': manifest['runtime'], 'analysis': manifest['analysis']}


def prepare_asset(folder, variant, provenance):
    """Publish derived bytes before the immutable v1 manifest. Preserve originals."""
    folder = Path(folder)
    source = folder / FILES[variant]
    data = source.read_bytes()
    path = folder / (variant + '.ingestion.json')
    prepared_path = folder / (variant + '.assembly.glb')
    if path.exists():
        manifest = json.loads(path.read_text())
        validate_manifest(manifest, digest(data))
    else:
        manifest, derived = ingest(data, provenance)
        if derived is not None:
            temp = prepared_path.with_suffix('.partial')
            temp.write_bytes(derived); temp.replace(prepared_path)
        temp = path.with_suffix('.partial')
        temp.write_text(json.dumps(manifest, indent=2, allow_nan=False)); temp.replace(path)
    if manifest['runtime']['artifact'] not in {'prepared', 'source'}:
        raise GenerationError('Unknown manifest runtime artifact.')
    chosen = prepared_path if manifest['runtime']['artifact'] == 'prepared' else source
    output = chosen.read_bytes()
    if digest(output) != manifest['runtime']['sha256'] or inspect_glb(output)['preflight'] != 'PASS':
        raise GenerationError('Manifest-bound runtime geometry changed or failed preflight; delivery stopped.')
    return manifest, chosen
