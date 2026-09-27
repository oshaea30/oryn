"""Replaceable intent adapters. Fixed endpoints, bounded responses, no retries or raw error logs."""
import json
import re
import urllib.request
from cognition import SCHEMA, INSTRUCTIONS, CommandError, validate_intent


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_config(provider, model, key):
    if provider not in ('openai', 'gemini') or not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}', model):
        raise CommandError('Choose a provider and enter its exact structured-output model ID.')
    if not isinstance(key, str) or not 10 <= len(key) <= 512 or not all(33 <= ord(c) <= 126 for c in key):
        raise CommandError('Enter a valid API key. It is kept only in this server process’s memory.')


def request_for(provider, model, key, question, state):
    validate_config(provider, model, key)
    # Only bounded annotations/IDs, not room images, GLBs, file paths or annotation histories.
    context = state['context']
    content = json.dumps({'question': question, 'selectedPartId': context['selectedPartId'],
                         'parts': context['parts']}, ensure_ascii=False)
    if provider == 'openai':
        url = 'https://api.openai.com/v1/responses'
        headers = {'Authorization': 'Bearer ' + key}
        body = {'model': model, 'store': False, 'max_output_tokens': 1024,
                'input': [{'role': 'developer', 'content': INSTRUCTIONS}, {'role': 'user', 'content': content}],
                'text': {'format': {'type': 'json_schema', 'name': 'oryn_intent', 'strict': True, 'schema': SCHEMA}}}
    else:
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent'
        headers = {'x-goog-api-key': key}
        body = {'systemInstruction': {'parts': [{'text': INSTRUCTIONS}]},
                'contents': [{'role': 'user', 'parts': [{'text': content}]}],
                'generationConfig': {'maxOutputTokens': 1024,
                    'responseFormat': {'text': {'mimeType': 'application/json', 'schema': SCHEMA}}}}
    headers['Content-Type'] = 'application/json'
    return urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')


def extract(provider, result):
    try:
        if provider == 'openai':
            if result.get('status') != 'completed':
                raise ValueError()
            fragments = [c['text'] for item in result['output'] if item.get('type') == 'message'
                         for c in item['content'] if c.get('type') == 'output_text']
            if any(c.get('type') == 'refusal' for item in result['output'] if item.get('type') == 'message' for c in item['content']):
                raise ValueError()
        else:
            candidates = result['candidates']
            if len(candidates) != 1 or candidates[0].get('finishReason') != 'STOP':
                raise ValueError()
            fragments = [p['text'] for p in candidates[0]['content']['parts'] if 'text' in p and not p.get('thought')]
        if len(fragments) != 1:
            raise ValueError()
        return validate_intent(json.loads(fragments[0]))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise CommandError('Provider response was incomplete, refused or malformed. No retry or action was performed.') from None


def interpret(provider, model, key, question, state, opener=None):
    request = request_for(provider, model, key, question, state)
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=45) as response:
            data = response.read(65537)
        if len(data) > 65536:
            raise ValueError()
        result = json.loads(data)
    except Exception:
        raise CommandError('Provider request failed or timed out. It may have incurred usage. No automatic retry; check provider billing before resubmitting.') from None
    return extract(provider, result)


def priced_body(selected_policy, question, state):
    # Request construction is shared with the original adapter; never accept a client-supplied body.
    request = request_for('openai', selected_policy['model'], 'unused-placeholder', question, state)
    body = json.loads(request.data)
    body['reasoning'] = {'effort': selected_policy['effort']}
    body['service_tier'] = 'default'
    body['max_output_tokens'] = selected_policy['max_output_tokens']
    return body


def openai_json(path, key, body, opener=None):
    if path not in ('responses', 'responses/input_tokens'):
        raise CommandError('Unsupported provider endpoint.')
    request = urllib.request.Request('https://api.openai.com/v1/' + path,
        data=json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode(),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}, method='POST')
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=45) as response:
            raw = response.read(65537)
        if len(raw) > 65536: raise ValueError()
        value = json.loads(raw)
        if not isinstance(value, dict): raise ValueError()
        return value
    except Exception:
        raise CommandError('Provider request failed or timed out. No automatic retry. Any reserved generation budget remains held.') from None


def count_input(key, body):
    # The count endpoint accepts the input-affecting fields, not generation-only
    # store/service_tier/max_output_tokens. Preserve the full schema and reasoning settings.
    if set(body) != {'model','store','max_output_tokens','input','text','reasoning','service_tier'}:
        raise CommandError('Unreviewed request fields; exact token counting blocked.')
    count_body = {name:body[name] for name in ('model','input','text','reasoning')}
    value = openai_json('responses/input_tokens', key, count_body)
    count = value.get('input_tokens')
    if type(count) is not int or count < 1:
        raise CommandError('Provider did not return an exact input count. Generation blocked.')
    return count


def generate_priced(key, body):
    return openai_json('responses', key, body)
