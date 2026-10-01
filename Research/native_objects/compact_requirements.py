"""Lossless row transport for the existing source-bound requirement contract.

No defaults, inference or omitted fields: each row restores all ten named fields.
Canonical requirements and their later validators remain authoritative.
"""
from copy import deepcopy
from Research.native_objects import assembly_arrangements as arrangements

FIELDS=('id','obligation','kind','subject','target','predicate','value','mode','basis','source')
EXCLUSION_FIELDS=('id','subject','domain','source')
KEYS={'requirements','exclusions','spatial','assemblies'}
INSTRUCTIONS='''
COMPACT REQUIREMENT TRANSPORT (overrides record syntax only):
Return each requirements item as a ten-string row in EXACT order:
[id, obligation, kind, subject, target, predicate, value, mode, basis, source].
Return each exclusions item as a four-string row: [id, subject, domain, source].
kind is exactly entity/relation/constraint/visual/behavior. mode, basis, obligation and predicates
use the enums specified above, not synonyms. All columns are mandatory, including empty strings
where the existing contract requires them.
Do not omit, merge, downgrade or truncate intent to shorten output. Keep values concise, preserving
qualifiers. spatial and assemblies retain their normal named fields and stable requirement IDs.
The application restores every named field exactly and runs the same semantic/coverage validators.
The inventory supports up to 48 requirements, consistent with the underlying contract. This is
capacity for additional assembly relationships, not a request to fill it. Emit necessary intent.
'''


def schema(request,roles):
    out=arrangements.schema(request,roles)
    for name,fields,limit in (('requirements',FIELDS,48),('exclusions',EXCLUSION_FIELDS,12)):
        out['properties'][name]={'type':'array','maxItems':limit,'items':{'type':'array',
            'items':{'type':'string'},'minItems':len(fields),'maxItems':len(fields),
            'description':'Exact column order: '+', '.join(fields)}}
    return out


def encode(raw):
    if not isinstance(raw,dict) or set(raw)!=KEYS:raise ValueError('Invalid canonical transport fields')
    out=deepcopy(raw)
    for name,fields in (('requirements',FIELDS),('exclusions',EXCLUSION_FIELDS)):
        if not isinstance(raw[name],list):raise ValueError('Invalid requirement collection')
        rows=[]
        for record in raw[name]:
            if not isinstance(record,dict) or set(record)!=set(fields) or any(not isinstance(record[k],str) for k in fields):
                raise ValueError('Canonical record must preserve every source-bound field')
            rows.append([record[k] for k in fields])
        out[name]=rows
    if decode(out)!=raw:raise ValueError('Requirement transport lost fields')
    return out


def decode(raw):
    if not isinstance(raw,dict) or set(raw)!=KEYS:raise ValueError('Invalid compact requirement fields')
    out=deepcopy(raw)
    for name,fields,limit in (('requirements',FIELDS,48),('exclusions',EXCLUSION_FIELDS,12)):
        if not isinstance(raw[name],list) or len(raw[name])>limit:raise ValueError('Compact requirement count limit')
        records=[]
        for row in raw[name]:
            if not isinstance(row,list) or len(row)!=len(fields) or any(not isinstance(v,str) for v in row):
                raise ValueError('Compact row needs every field in its declared position')
            records.append(dict(zip(fields,row)))
        out[name]=records
    return out
