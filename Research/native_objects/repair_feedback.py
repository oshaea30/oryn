"""Preserve measured predicates across repair; never lock poses or edit geometry."""
from copy import deepcopy
import json
from Research.native_objects.intent_requirements import digest

INSTRUCTIONS='''
MEASURED REPAIR BASELINE:
application_feedback.preserve contains facts already measured true by the application. Preserve
these while fixing failed_geometry_checks. Each group member relation is reported separately from
whether the geometry underneath its port is valid: repairing a feature must not reverse an already
correct signed axis or break an already correct row/ring. The original frozen requirements, feature
bindings and assembly constraints still apply. Dimensions and poses may change if ALL those measured
predicates remain true. Do not delete a check, weaken a requirement or substitute a different port.
A repair is rejected if any preserved fact becomes false or disappears. This is a numeric regression
check, not evidence that the object is visually coherent or its chosen features have correct meaning.
'''


def _normal(value):
    # Locked constraints permit 0 and 0.0 to mean the same numeric requirement.
    if isinstance(value,bool):return value
    if isinstance(value,(int,float)):return float(value)
    if isinstance(value,dict):return {k:_normal(v) for k,v in value.items()}
    if isinstance(value,list):return [_normal(v) for v in value]
    return value


def _key(identity):return json.dumps(_normal(identity),sort_keys=True,separators=(',',':'))


def facts(report):
    """Return stable identities and truth values, including partial group successes."""
    values={}
    def add(identity,passed):
        key=_key(identity)
        if key in values or not isinstance(passed,bool):raise ValueError('Ambiguous measured repair fact')
        values[key]={'identity':deepcopy(identity),'passed':passed}
    for check in report['checks']:
        identity={k:deepcopy(check[k]) for k in ('kind','relation','requirement_id','assembly_id','aspect') if k in check}
        if len(identity)<2:raise ValueError('Measured repair fact lacks stable identity')
        if identity['kind']=='assembly_interference' and set(identity.get('relation',{}))=={'a','b'}:
            identity['relation']=dict(zip(('a','b'),sorted(identity['relation'].values())))
        add(identity,check['passed'])
        if check['kind']=='assembly_arrangement':
            for member in check['measurement'].get('members',[]):
                if 'relation_passed' in member:
                    add({**identity,'facet':'member_relation','part':member['part'],'port':member['port']},member['relation_passed'])
    return values


def snapshot(report):
    passed=[v['identity'] for _,v in sorted(facts(report).items()) if v['passed']]
    payload={'version':1,'passed_facts':passed}
    return {**payload,'sha256':digest(payload)}


def validate(snapshot):
    if not isinstance(snapshot,dict) or set(snapshot)!={'version','passed_facts','sha256'} or snapshot['version']!=1:
        raise ValueError('Invalid measured repair baseline')
    payload={k:snapshot[k] for k in ('version','passed_facts')}
    if digest(payload)!=snapshot['sha256']:raise ValueError('Measured repair baseline changed')
    if not isinstance(snapshot['passed_facts'],list) or len({_key(v) for v in snapshot['passed_facts']})!=len(snapshot['passed_facts']):
        raise ValueError('Invalid measured repair identities')


def regressions(baseline,report):
    validate(baseline);current=facts(report);failed=[]
    for identity in baseline['passed_facts']:
        now=current.get(_key(identity))
        if now is None or not now['passed']:
            failed.append({'identity':deepcopy(identity),'reason':'measurement_missing' if now is None else 'previously_passing_fact_failed'})
    return {'baseline_sha256':baseline['sha256'],'preserved_fact_count':len(baseline['passed_facts']),
            'passed':not failed,'regressions':failed}


def feedback(report,baseline):
    """Compact readable fact list; full measurements remain in the saved report."""
    validate(baseline)
    return {'failed_geometry_checks':[c for c in report['checks'] if not c['passed']],
            'preserve':{'baseline_sha256':baseline['sha256'],'facts':deepcopy(baseline['passed_facts']),
                'scope':'Previously true measured predicates. Poses and dimensions are not frozen.'}}
