"""Bounded, local-only geometry evidence. No credentials, providers or XR writes.

Views are diagnostic orthographic SVGs in source-node coordinates, not photos,
engineering drawings or ground-truth visibility. Candidate knowledge lives in
separate immutable revisions; it never upgrades the ingestion manifest.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import threading
import time
from typing import Protocol
import zlib

from ingestion import digest, validate_manifest
from mesh_islands import bounds, components, decode
from providers import MAX_BYTES
from workflow import encoded, fingerprint

VERSION = 'oryn-geometry-evidence-v1'
MAX_TARGETS = 8
MAX_FACES = 20000
MAX_PIECES = 2048
MAX_VIEW_BYTES = 16*1024*1024
MAX_STORED_VIEW_BYTES = 256*1024*1024
VIEWS = (('XY', (1, 0, 0), (0, 1, 0), (0, 0, 1)),
         ('ZY', (0, 0, 1), (0, 1, 0), (-1, 0, 0)),
         ('XZ', (1, 0, 0), (0, 0, -1), (0, 1, 0)),
         ('ISO', (.707107, 0, -.707107), (-.408248, .816497, -.408248), (.57735, .57735, .57735)))


class MappingCognitiveProvider(Protocol):
    """Replaceable mapping boundary; application owns admission and persistence."""
    def propose_mappings(self, episode, package, references, images, record_event) -> tuple: ...


def gap(a, b):
    """Lower bound on separation of axis-aligned boxes, NOT surface distance."""
    return math.sqrt(sum(max(0, a['min'][i]-b['max'][i], b['min'][i]-a['max'][i])**2 for i in range(3)))


def contact_sheet(points, faces, selected):
    selected = set(selected)
    used = sorted({v for i in selected for v in faces[i]})
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 540" role="img" aria-label="Four context views and four isolated views">',
           '<rect width="1000" height="540" fill="#10171e"/>']
    for row in range(2):
        for column, (name, right, up, depth) in enumerate(VIEWS):
            projected = [tuple(sum(p[i]*axis[i] for i in range(3)) for axis in (right, up, depth)) for p in points]
            fit = [projected[v] for v in (used if row else range(len(points)))]
            box = bounds(fit)
            span = max(box['size'][0], box['size'][1], 1e-12)
            scale = 208/span
            ox, oy = column*250, row*270
            svg.append(f'<text x="{ox+12}" y="{oy+22}" fill="#b1c2cf" font-size="13">{name} / {"isolated" if row else "context"}</text>')
            svg.append(f'<text x="{ox+12}" y="{oy+257}" fill="#94b1bf" font-size="10">208 px = {span:.5g} source units</text>')
            indices = selected if row else range(len(faces))
            # Painter order is an explicit preview approximation, not a z-buffer.
            for face_id in sorted(indices, key=lambda n: (sum(projected[v][2] for v in faces[n]), n)):
                coords = ' '.join(f'{ox+125+(projected[v][0]-box["center"][0])*scale:.2f},{oy+136-(projected[v][1]-box["center"][1])*scale:.2f}' for v in faces[face_id])
                color = '#6fe3bd' if face_id in selected else '#445460'
                svg.append(f'<polygon points="{coords}" fill="{color}" stroke="#10171e" stroke-width="0.15"/>')
    svg.append('</svg>')
    return ''.join(svg)


def build_evidence(data, manifest, targets):
    validate_manifest(manifest, digest(data))
    if not isinstance(targets, list) or not 1 <= len(targets) <= MAX_TARGETS or len(set(targets)) != len(targets):
        raise ValueError('Evidence requires one to eight distinct investigation targets.')
    doc, points, faces = decode(data)  # Unsupported layouts fail closed, unchanged.
    if len(faces) > MAX_FACES or len(points) > MAX_FACES*3:
        raise ValueError('Local evidence geometry budget exceeded.')
    islands = components(points, faces)
    pieces = manifest['geometry_pieces']
    if len(islands) != len(pieces) or len(pieces) > MAX_PIECES:
        raise ValueError('Evidence topology does not match the bound manifest.')
    measurements = []
    for n, (piece, face_ids) in enumerate(zip(pieces, islands), 1):
        expected = manifest['asset_id'] + f':island:{n:03}'
        if piece['id'] != expected or piece.get('triangle_indices') != face_ids:
            raise ValueError('Evidence piece binding changed.')
        used = sorted({v for i in face_ids for v in faces[i]})
        measurements.append({'geometry_id': expected, 'triangles': len(face_ids), 'vertices': len(used),
                             'bounds_local': bounds([points[v] for v in used]), 'status': 'unidentified'})
    by_id = {p['geometry_id']: p for p in measurements}
    if any(t not in by_id for t in targets):
        raise ValueError('Unknown investigation target.')
    views = []
    for target in targets:
        measurement = by_id[target]
        neighbors = sorted(({'geometry_id': p['geometry_id'], 'aabb_gap_local': gap(measurement['bounds_local'], p['bounds_local'])}
                            for p in measurements if p['geometry_id'] != target), key=lambda p: (p['aabb_gap_local'], p['geometry_id']))[:3]
        piece = pieces[measurements.index(measurement)]
        svg = contact_sheet(points, faces, piece['triangle_indices'])
        views.append({'geometry_id': target, 'view_id': digest(svg.encode()), 'svg': svg,
                      'nearest_bounds': neighbors})
    return {'version': VERSION, 'asset_id': manifest['asset_id'], 'coordinate_frame': 'source_node_local',
            'source_node_transform': {k: doc['nodes'][0][k] for k in ('matrix','translation','rotation','scale') if k in doc['nodes'][0]},
            'measurements': measurements, 'views': views, 'targets': targets,
            'limitations': ['Disconnected surfaces are not identified mechanical components.',
                'Nearest bounds are not adjacency, physical contact or assembly relationships.',
                'Source units and orientation are unverified; node transforms are recorded but not applied to diagnostic views.',
                'Orthographic painter-order previews may have occlusion artifacts; isolated views rescale each piece.',
                'Eight targets are a work budget, not a claim that they are the most important components.'],
            'outbound_images': False, 'mapping_status': 'awaiting_vision_policy_and_provider',
            'component_mappings': [], 'runtime_changed': False}


def validate_candidates(result, package, references, provenance):
    """Strict provider output contract. Evidence links support review, not truth."""
    if not isinstance(result, dict) or set(result) != {'mappings', 'unknown_geometry_ids'}:
        raise ValueError('Invalid mapping response fields.')
    if not isinstance(provenance, dict) or set(provenance) != {'method','provider','model','operation_id'} or provenance['method'] != 'multimodal_model' or any(not isinstance(v,str) or not 1 <= len(v) <= 200 for v in provenance.values()):
        raise ValueError('Explicit model and operation provenance required.')
    sources = {s['id']: s for s in references}
    if len(sources) != len(references) or any(not s.get('content_sha256') or not s.get('url') for s in references):
        raise ValueError('Content-bound reference evidence required.')
    allowed = set(package['targets']); seen = set()
    mappings = result['mappings']; unknown = result['unknown_geometry_ids']
    if not isinstance(mappings,list) or len(mappings) > MAX_TARGETS or not isinstance(unknown,list):
        raise ValueError('Mapping batch budget exceeded.')
    for mapping in mappings:
        if not isinstance(mapping,dict) or set(mapping) != {'geometry_id','candidate_name','rationale','source_ids','view_ids'}:
            raise ValueError('Unsupported mapping fields or epistemic promotion.')
        gid = mapping['geometry_id']
        if not isinstance(gid,str) or gid not in allowed or gid in seen:
            raise ValueError('Unknown or duplicate mapped geometry.')
        if any(not isinstance(mapping[k],str) or not 1 <= len(mapping[k].strip()) <= 500 for k in ('candidate_name','rationale')):
            raise ValueError('Bounded candidate name and rationale required.')
        for field, valid in (('source_ids', set(sources)), ('view_ids', {v['view_id'] for v in package['views'] if v['geometry_id']==gid})):
            ids = mapping[field]
            if not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids) or len(set(ids)) != len(ids) or not set(ids) <= valid:
                raise ValueError('Candidate requires matching view and reference evidence.')
        seen.add(gid)
    if any(not isinstance(i,str) for i in unknown) or len(set(unknown)) != len(unknown) or seen.intersection(unknown) or seen.union(unknown) != allowed:
        raise ValueError('Every selected piece must be a candidate or explicitly unknown.')
    annotated=[{**deepcopy(mapping), 'status':'candidate', 'derived_by':deepcopy(provenance),
                'human_review':{'status':'not_reviewed'}} for mapping in mappings]
    return {'status': 'candidate', 'human_review': {'status': 'not_reviewed'},
            'derived_by': deepcopy(provenance), 'mappings': annotated,
            'unknown_geometry_ids': list(unknown), 'evidence_package_id': package['id'],
            'reference_evidence': deepcopy(references), 'capabilities_promoted': False}


class GeometryEvidenceStore:
    def __init__(self, workflows):
        self.workflows = workflows
        with workflows.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS geometry_evidence
                (id TEXT PRIMARY KEY, status TEXT NOT NULL, record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS geometry_candidates
                (id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL, record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS geometry_evidence_views
                (evidence_id TEXT NOT NULL, ordinal INTEGER NOT NULL, svg BLOB NOT NULL,
                 PRIMARY KEY(evidence_id,ordinal));''')
            # Lossless storage migration for early local previews; hashes/IDs stay
            # unchanged. Freed SQLite pages are reused, not forcibly vacuumed.
            old=db.execute("SELECT evidence_id,ordinal FROM geometry_evidence_views WHERE typeof(svg)='text'").fetchall()
            for identifier, ordinal in old:
                svg=db.execute('SELECT svg FROM geometry_evidence_views WHERE evidence_id=? AND ordinal=?',(identifier,ordinal)).fetchone()[0]
                db.execute('UPDATE geometry_evidence_views SET svg=? WHERE evidence_id=? AND ordinal=?',(zlib.compress(svg.encode()),identifier,ordinal))

    def enqueue(self, source, manifest, targets):
        identity = {'version': VERSION, 'asset_id': manifest['asset_id'], 'manifest': manifest, 'targets': targets}
        # Delivery provenance must not create duplicate evidence for reused assets.
        identity['manifest'] = {k:v for k,v in manifest.items() if k != 'provenance'}
        identifier = fingerprint(identity)
        record = {'id': identifier, **identity, 'status': 'queued', 'source_path': str(source),
                  'created_at': time.time(), 'actual_cost_nanos': 0, 'outbound_images': False}
        with self.workflows.connect() as db:
            db.execute('INSERT OR IGNORE INTO geometry_evidence VALUES (?,?,?)', (identifier,'queued',encoded(record)))
        return identifier

    def get(self, identifier):
        with self.workflows.connect() as db:
            row = db.execute('SELECT record FROM geometry_evidence WHERE id=?',(identifier,)).fetchone()
        if not row: raise ValueError('Unknown geometry evidence.')
        return json.loads(row[0])

    def summary(self, identifier):
        record = self.get(identifier)
        return {k:record[k] for k in ('id','status','asset_id','targets','actual_cost_nanos','outbound_images','latency_ms','error') if k in record}

    def view(self, identifier, ordinal):
        if type(ordinal) is not int or not 0 <= ordinal < MAX_TARGETS:
            raise ValueError('Invalid view ordinal.')
        record=self.get(identifier)
        if record['status'] != 'ready' or ordinal >= len(record['views']):
            raise ValueError('Evidence view unavailable.')
        with self.workflows.connect() as db:
            row=db.execute('SELECT svg FROM geometry_evidence_views WHERE evidence_id=? AND ordinal=?',(identifier,ordinal)).fetchone()
        if not row: raise ValueError('Evidence view unavailable.')
        decoder=zlib.decompressobj()
        try:
            raw=decoder.decompress(row[0],MAX_VIEW_BYTES+1)
            if len(raw)>MAX_VIEW_BYTES or not decoder.eof or decoder.unused_data: raise ValueError('Invalid compressed view.')
            svg=raw.decode()
        except (zlib.error,UnicodeError,TypeError):
            raise ValueError('Evidence view failed decompression.') from None
        if digest(raw) != record['views'][ordinal]['view_id']:
            raise ValueError('Evidence view failed integrity check.')
        return svg

    def report(self, identifier):
        record = self.get(identifier)
        result = {k:v for k,v in record.items() if k not in {'source_path','manifest'}}
        if 'views' in result:
            result['views'] = [{k:v for k,v in view.items() if k != 'svg'} for view in result['views']]
        with self.workflows.connect() as db:
            result['candidate_revisions'] = [json.loads(r[0]) for r in db.execute('SELECT record FROM geometry_candidates WHERE evidence_id=? ORDER BY id',(identifier,))]
        return result

    def save_candidates(self, identifier, result, references, provenance):
        package = self.get(identifier)
        if package['status'] != 'ready': raise ValueError('Ready geometry evidence required.')
        record = validate_candidates(result, package, references, provenance)
        record['id'] = fingerprint(record)
        with self.workflows.connect() as db:
            db.execute('INSERT OR IGNORE INTO geometry_candidates VALUES (?,?,?)',(record['id'],identifier,encoded(record)))
        return record

    def recover_interrupted(self):
        with self.workflows.connect() as db:
            rows = db.execute("SELECT id,record FROM geometry_evidence WHERE status='running'").fetchall()
            for identifier, raw in rows:
                record=json.loads(raw); record.update(status='interrupted',error='Local evidence preparation interrupted; no automatic retry.')
                db.execute('UPDATE geometry_evidence SET status=?,record=? WHERE id=?',('interrupted',encoded(record),identifier))

    def run_next(self):
        with self.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT id,record FROM geometry_evidence WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row: return None
            identifier, raw=row; record=json.loads(raw); record['status']='running'
            db.execute('UPDATE geometry_evidence SET status=?,record=? WHERE id=?',('running',encoded(record),identifier))
        start=time.perf_counter(); images=[]
        try:
            path=Path(record['source_path'])
            if path.stat().st_size > MAX_BYTES: raise ValueError('Source exceeds budget.')
            if shutil.disk_usage(path.parent).free < 576*1024*1024:
                raise ValueError('Preserve local free-space reserve.')
            result=build_evidence(path.read_bytes(),record['manifest'],record['targets'])
            images=[v.pop('svg') for v in result['views']]
            if any(len(svg)>MAX_VIEW_BYTES for svg in images) or sum(len(svg) for svg in images) > 64*1024*1024:
                raise ValueError('Local view storage budget exceeded.')
            images=[zlib.compress(svg.encode()) for svg in images]
            record.update(result,status='ready')
        except Exception:
            record.update(status='unavailable',error='Local evidence unavailable: source binding, layout or geometry budget failed validation. Original model preserved.')
        record['latency_ms']=(time.perf_counter()-start)*1000
        with self.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            stored=db.execute('SELECT COALESCE(SUM(LENGTH(svg)),0) FROM geometry_evidence_views').fetchone()[0]
            if record['status']=='ready' and stored+sum(map(len,images))>MAX_STORED_VIEW_BYTES:
                record.update(status='unavailable',error='Local evidence storage quota reached. Existing assets preserved; no automatic eviction.')
            if record['status']=='ready':
                db.executemany('INSERT INTO geometry_evidence_views VALUES (?,?,?)',[(identifier,n,svg) for n,svg in enumerate(images)])
            db.execute('UPDATE geometry_evidence SET status=?,record=? WHERE id=?',(record['status'],encoded(record),identifier))
        return self.summary(identifier)

    def start(self):
        if getattr(self,'thread',None) is not None: return
        self.recover_interrupted()
        self.stop_event=threading.Event()
        def work():
            while not self.stop_event.is_set():
                try:
                    if self.run_next() is None: self.stop_event.wait(1)
                except Exception:
                    return  # Store failure must never impact delivery or paid work.
        self.thread=threading.Thread(target=work,daemon=True,name='oryn-local-evidence')
        self.thread.start()

    def stop(self):
        self.stop_event.set()
