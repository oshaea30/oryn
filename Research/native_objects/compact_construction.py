"""Lossless transport adapter for the unchanged executable-connection geometry API.

Shapes are authored by the model for this request and may be referenced by multiple
instances. Defaults remove redundant fields; no object templates or new geometry ops.
"""
from copy import deepcopy
import json
from Research.native_objects import assembly_connections as assembly
from Research.native_objects import intent_requirements as intent
from Research.native_objects import construction as base

DETAIL=base.object_schema({'key':{'type':'string','enum':['wall','radius','sections','repeat','step']},'values':base.VEC})
FORM=base.object_schema({'kind':deepcopy(assembly.SCHEMA['properties']['parts']['items']['properties']['forms']['items']['properties']['kind']),
                       'size':base.VEC,'at':base.VEC,'rotate':base.VEC,
                       'op':{'type':'string','enum':['add','subtract']},'detail':base.arr(DETAIL)})
SCHEMA=base.object_schema({'shapes':base.arr(base.object_schema({'id':base.TEXT,'forms':base.arr(FORM)})),
 'parts':base.arr(base.object_schema({'id':base.TEXT,'entity':base.TEXT,'parent':base.TEXT,'shape':base.TEXT,'color':base.VEC})),
 'root_position':base.VEC,'root_rotation':base.VEC,
 **{k:deepcopy(assembly.SCHEMA['properties'][k]) for k in ('ports','mates','containments','clearances','symmetries')},
 'bindings':base.arr(intent.BINDING_SCHEMA)})
INSTRUCTIONS=assembly.INSTRUCTIONS+'''
COMPACT TRANSPORT AND REQUIREMENT COVERAGE (overrides earlier output shape):
Return the compact schema. The application expands it into the SAME geometry executor.
shapes holds request-specific form definitions. parts reference shape IDs; repeated components may
share one shape but MUST retain separate part IDs. These are your designs, never library object recipes.
Each part entity references a frozen requirement entity ID; the application derives the role string.
All nonroot poses are omitted and solved from mates. root_position/root_rotation supply the root pose.
Form fields: kind, size, at, rotate, op, detail. at=[] and rotate=[] mean zero vectors.
Defaults: wall=0, radius=0, sections=[], repeat=[1,1,1], step=[0,0,0]. Supply only nondefault
options in detail, each at most once. wall/radius have one number; repeat/step three numbers;
sections flattens the existing five-number loft rows into one numeric array. No new operations.
Do not repeat explanations or unused default options. Keep output compact; reuse shared shapes.

If the inventory includes mode/basis/exclusions, preserve these distinctions. Appearance denotes
visual realization, structure denotes static relationships, behavior denotes a runtime effect.
Physical-verification and exact-identity claims need matching evidence, not an attractive model.
An inferred relationship is a proposed requirement, never an externally verified fact. Exclusions
waive only their named scope; they do not erase other requirements. Do not reclassify any requirement.
The frozen inventory is authoritative for coverage. Preserve every requirement ID exactly once in
bindings. Never rewrite, omit or downgrade requirements. original request remains authoritative for
meaning; preserve important intent beyond mere labels. Each binding has id, kind, refs, note.
exists/count/appearance => kind components and refs ['part:ID',...] listing ALL parts for the subject
entity; an object appearance binding covers all parts. Appearance remains visually unverified.
inside => kind relations and refs ['containment:INDEX',...] matching inner subject and outer target;
INDEX is zero-based in the containments array. A parent link or attachment does not imply inside.
attached/connected => kind relations, refs ['mate:MATE_ID',...] proving the direct mate or graph path.
clearance => kind constraint, refs ['clearance:INDEX',...] matching endpoints and at least the minimum.
capability => kind capability, refs ['capability:NAME'] only for inspect/geometric_explode/reassemble.
Other capabilities (including emission/animate/physical_function) are unsupported by this executor.
Unsupported or evidence-required items => kind unsupported, refs=[], note giving a brief honest reason.
Unsupported is explicit coverage, never fulfillment. Required/evidence-required unsupported items
block geometry; optional/design_choice unsupported items are disclosed. Do not fake supported bindings.
An optional/design_choice entity explicitly bound unsupported may be omitted.
Use note='' for supported bindings. Bind to actual entities and relationships, not prose reassurance.
The deterministic gate runs BEFORE geometry. A missing/mistyped/unrelated binding returns errors for
one bounded repair. If the gate allows execution, measurable geometry checks still need to pass.
'''


def expand(raw,contract):
    if not isinstance(raw,dict) or set(raw)!=set(SCHEMA['required']):raise ValueError('Invalid compact plan fields')
    if not isinstance(raw['shapes'],list) or not 0<=len(raw['shapes'])<=32 or not isinstance(raw['parts'],list) or not 0<=len(raw['parts'])<=32:raise ValueError('Compact size limit')
    shapes={};used=set();entities={e['id']:e['role'] for e in contract['inventory']['entities']}
    for shape in raw['shapes']:
        if not isinstance(shape,dict) or set(shape)!={'id','forms'} or not intent.ident(shape['id']) or shape['id'] in shapes:raise ValueError('Invalid shape ID')
        if not isinstance(shape['forms'],list) or not 1<=len(shape['forms'])<=16:raise ValueError('Form count limit')
        forms=[]
        for f in shape['forms']:
            if not isinstance(f,dict) or set(f)!=set(FORM['required']):raise ValueError('Invalid compact form')
            full={'kind':f['kind'],'size':deepcopy(f['size']),'offset':deepcopy(f['at']) if f['at'] else [0,0,0],
                  'rotation':deepcopy(f['rotate']) if f['rotate'] else [0,0,0],'operation':f['op'],
                  'wall':0,'radius':0,'sections':[],'repeat':[1,1,1],'step':[0,0,0]}
            if not isinstance(f['detail'],list) or len(f['detail'])>5:raise ValueError('Detail count limit')
            seen=set()
            for option in f['detail']:
                if not isinstance(option,dict) or set(option)!={'key','values'}:raise ValueError('Invalid form detail')
                key,values=option['key'],option['values']
                if key not in ('wall','radius','sections','repeat','step') or key in seen or not isinstance(values,list):raise ValueError('Invalid/duplicate form detail')
                seen.add(key)
                if key in ('wall','radius'):
                    if len(values)!=1:raise ValueError('Scalar detail needs one value')
                    full[key]=values[0]
                elif key in ('repeat','step'):
                    if len(values)!=3:raise ValueError('Vector detail needs three values')
                    full[key]=deepcopy(values)
                else:
                    if len(values)%5 or not 10<=len(values)<=60:raise ValueError('Loft detail needs five-number rows')
                    full[key]=[values[i:i+5] for i in range(0,len(values),5)]
            forms.append(full)
        shapes[shape['id']]=forms
    out={'assumptions':['Generic model design; requirement coverage does not verify semantics or engineering.'],
         'limitations':['Geometry executor unchanged; unsupported requirements are explicit.'],
         'parts':[],'mounts':[],'passages':[],**{k:deepcopy(raw[k]) for k in ('ports','mates','containments','clearances','symmetries')}}
    for p in raw['parts']:
        if not isinstance(p,dict) or set(p)!={'id','entity','parent','shape','color'} or p['entity'] not in entities or p['shape'] not in shapes:raise ValueError('Invalid part references')
        used.add(p['shape'])
        out['parts'].append({'id':p['id'],'role':entities[p['entity']],'parent':p['parent'],
             'position':deepcopy(raw['root_position']) if not p['parent'] else [0,0,0],
             'rotation':deepcopy(raw['root_rotation']) if not p['parent'] else [0,0,0],
             'forms':deepcopy(shapes[p['shape']]),'color':deepcopy(p['color'])})
    if used!=set(shapes):raise ValueError('Unused shape definitions')
    if out['parts']:
        assembly.validate(out,sorted({p['role'] for p in out['parts']}))  # Syntax/tree only.
    elif any(out[k] for k in ('ports','mates','containments','clearances','symmetries')):
        raise ValueError('Empty unsupported plan cannot contain geometry references')
    return out


def pack(plan,contract,bindings):
    """Offline round-trip audit only. Never injected into a live model prompt."""
    entities={e['role']:e['id'] for e in contract['inventory']['entities']};shapes=[];lookup={};parts=[]
    for part in plan['parts']:
        key=json.dumps(part['forms'],sort_keys=True)
        if key not in lookup:
            sid='shape_'+str(len(shapes));lookup[key]=sid;forms=[]
            for f in part['forms']:
                detail=[]
                for name,default in [('wall',0),('radius',0),('sections',[]),('repeat',[1,1,1]),('step',[0,0,0])]:
                    if f[name]!=default:
                        values=([f[name]] if name in ('wall','radius') else [x for row in f[name] for x in row] if name=='sections' else f[name])
                        detail.append({'key':name,'values':deepcopy(values)})
                forms.append({'kind':f['kind'],'size':deepcopy(f['size']),'at':deepcopy(f['offset']) if any(f['offset']) else [],
                              'rotate':deepcopy(f['rotation']) if any(f['rotation']) else [],'op':f['operation'],'detail':detail})
            shapes.append({'id':sid,'forms':forms})
        parts.append({'id':part['id'],'entity':entities[part['role']],'parent':part['parent'],'shape':lookup[key],'color':deepcopy(part['color'])})
    root=next(p for p in plan['parts'] if not p['parent'])
    return {'shapes':shapes,'parts':parts,'root_position':deepcopy(root['position']),'root_rotation':deepcopy(root['rotation']),
            **{k:deepcopy(plan[k]) for k in ('ports','mates','containments','clearances','symmetries')},'bindings':deepcopy(bindings)}
