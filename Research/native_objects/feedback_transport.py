"""Lossless tables for repeated measured-fact identities; no filtering or changed checks."""
from copy import deepcopy
import re
from Research.native_objects import repair_feedback

INSTRUCTIONS='''
PRESERVATION TABLES:
application_feedback.preserve.fact_tables encodes ALL prior passing facts in order.
Each table fixes kind; columns are dotted nested-field paths; each row gives their values.
Reconstruct each complete fact. The original full checks remain enforced.
'''


def flatten(value,prefix=''):
    if not isinstance(value,dict):raise ValueError('Expected fact object')
    fields={}
    for key,val in sorted(value.items()):
        if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9_]*',key):raise ValueError('Invalid fact field')
        path=prefix+'.'+key if prefix else key
        if isinstance(val,dict):
            if not val:raise ValueError('Empty nested fact')
            fields.update(flatten(val,path))
        else:fields[path]=deepcopy(val)
    return fields


def inflate(fields):
    result={}
    for path,value in fields.items():
        names=path.split('.')
        if any(not re.fullmatch('[a-z][a-z0-9_]*',n) for n in names):raise ValueError('Invalid fact path')
        target=result
        for name in names[:-1]:
            if name not in target:target[name]={}
            if not isinstance(target[name],dict):raise ValueError('Conflicting fact path')
            target=target[name]
        if names[-1] in target:raise ValueError('Duplicate fact path')
        target[names[-1]]=deepcopy(value)
    return result


def encode(value):
    out=deepcopy(value);preserve=out['preserve'];facts=preserve.pop('facts');tables=[]
    if 'fact_tables' in preserve or not isinstance(facts,list):raise ValueError('Invalid feedback transport')
    for fact in facts:
        fields=flatten(fact);kind=fields.pop('kind');columns=list(fields)
        if not isinstance(kind,str):raise ValueError('Invalid fact kind')
        if not tables or tables[-1]['kind']!=kind or tables[-1]['columns']!=columns:
            tables.append({'kind':kind,'columns':columns,'rows':[]})
        tables[-1]['rows'].append([fields[c] for c in columns])
    preserve['fact_tables']=tables
    if decode(out)!=value:raise ValueError('Feedback round trip changed a fact')
    return out


def decode(value):
    out=deepcopy(value);preserve=out['preserve'];tables=preserve.pop('fact_tables');facts=[]
    if 'facts' in preserve or not isinstance(tables,list):raise ValueError('Invalid feedback tables')
    for table in tables:
        if not isinstance(table,dict) or set(table)!={'kind','columns','rows'} or not isinstance(table['kind'],str):raise ValueError('Invalid fact table')
        columns=table['columns']
        if not isinstance(columns,list) or any(not isinstance(c,str) for c in columns) or len(set(columns))!=len(columns) or 'kind' in columns:raise ValueError('Invalid table columns')
        if not isinstance(table['rows'],list):raise ValueError('Invalid table rows')
        for row in table['rows']:
            if not isinstance(row,list) or len(row)!=len(columns):raise ValueError('Invalid table row')
            facts.append(inflate({'kind':table['kind'],**dict(zip(columns,row))}))
    preserve['facts']=facts
    return out


def audit(value,encoded):
    decoded=decode(encoded)
    if decoded!=value:raise ValueError('Feedback round trip changed')
    return {'fact_count':len(value['preserve']['facts']),'table_count':len(encoded['preserve']['fact_tables']),
        'exact_roundtrip':True,'uncompressed_sha256':repair_feedback.digest(value),
        'decoded_sha256':repair_feedback.digest(decoded),'all_failures_and_passed_facts_retained':True}
