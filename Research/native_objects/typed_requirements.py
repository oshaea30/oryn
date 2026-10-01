"""Lossless short-key transport preserving every canonical output-schema constraint.

Prepared after Assembly 011; not used to reinterpret or repair its recorded responses.
Unlike positional rows, short-key records keep the provider's enum/type constraints.
"""
from copy import deepcopy
from Research.native_objects import compact_requirements as rows

REQUIREMENT_KEYS=dict(zip(rows.FIELDS,('i','o','k','s','t','p','v','m','b','q')))
EXCLUSION_KEYS=dict(zip(rows.EXCLUSION_FIELDS,('i','s','d','q')))
INSTRUCTIONS='''
COMPACT TYPED REQUIREMENT TRANSPORT (overrides property names only):
Requirement keys: i=id, o=obligation, k=kind, s=subject, t=target, p=predicate, v=value,
m=mode, b=basis, q=source. Exclusion keys: i=id, s=subject, d=domain, q=source.
Every field remains mandatory. Values and their enums are UNCHANGED. Do not abbreviate values.
In particular exclusion domain motion differs from the positive capability animate.
spatial and assemblies retain their full property names. Preserve all intent, qualifications,
source references and required/optional/design-choice/evidence distinctions. No invented defaults.
The application expands keys exactly before applying canonical source, meaning and coverage checks.
Keep up to 48 requirements within the unchanged response allowance. Capacity is not a target count.
'''


def _schema(node,mapping):
    if 'anyOf' in node:return {**deepcopy(node),'anyOf':[_schema(v,mapping) for v in node['anyOf']]}
    if set(node['properties'])!=set(mapping) or set(node['required'])!=set(mapping):raise ValueError('Canonical record schema changed')
    out=deepcopy(node);out['properties']={mapping[k]:deepcopy(v) for k,v in node['properties'].items()}
    out['required']=[mapping[k] for k in node['required']];return out


def schema(request,roles):
    out=rows.arrangements.schema(request,roles)
    for name,mapping,limit in (('requirements',REQUIREMENT_KEYS,48),('exclusions',EXCLUSION_KEYS,12)):
        out['properties'][name]['items']=_schema(out['properties'][name]['items'],mapping)
        out['properties'][name]['maxItems']=limit
    return out


def _convert(raw,inverse):
    if not isinstance(raw,dict) or set(raw)!=rows.KEYS:raise ValueError('Invalid typed compact fields')
    out=deepcopy(raw)
    for name,mapping,limit in (('requirements',REQUIREMENT_KEYS,48),('exclusions',EXCLUSION_KEYS,12)):
        if inverse:mapping={v:k for k,v in mapping.items()}
        if not isinstance(raw[name],list) or len(raw[name])>limit:raise ValueError('Typed compact count limit')
        converted=[]
        for record in raw[name]:
            if not isinstance(record,dict) or set(record)!=set(mapping) or any(not isinstance(v,str) for v in record.values()):
                raise ValueError('Typed compact record must preserve every field')
            converted.append({mapping[k]:v for k,v in record.items()})
        out[name]=converted
    return out


def encode(raw):
    out=_convert(raw,False)
    if decode(out)!=raw:raise ValueError('Typed compact transport lost fields')
    return out


def decode(raw):return _convert(raw,True)
