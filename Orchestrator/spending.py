"""Reviewed, fail-closed development policy. All money is integer USD nanodollars."""
import hashlib
import json
from datetime import datetime, timezone
from cognition import CommandError

USD = 1_000_000_000
DAILY_LIMIT = 2 * USD
MAX_OUTPUT = 1024
PRICE_VERSION = 'openai-standard-text-2026-09-27-v1'
# Explicit review expiry, not silently refreshed at startup. No auto pricing downloads.
PRICE_REVIEWED = 1790467200  # 2026-09-27 00:00 UTC
PRICE_EXPIRES = 1791072000   # 2026-10-04 00:00 UTC
MODELS = {
    'gpt-6-sol': {'input': 2000, 'cached': 200, 'cache_write': 2500, 'output': 10000},
    'gpt-6-astra': {'input': 10000, 'cached': 1000, 'cache_write': 12500, 'output': 50000},
}
# Rates above are nanodollars/token, equivalent to the published USD/million rates.
PROFILES = {
    'routine': ('gpt-6-sol', 'medium', 30_000_000),
    'question': ('gpt-6-sol', 'medium', 50_000_000),
    'question_high': ('gpt-6-sol', 'high', 50_000_000),
    'vision': ('gpt-6-sol', 'medium', 50_000_000),
    'benchmark': ('gpt-6-astra', 'medium', 100_000_000),
    'benchmark_high': ('gpt-6-astra', 'high', 100_000_000),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def policy(provider, profile, now):
    if provider != 'openai' or not isinstance(profile, str) or profile not in PROFILES:
        raise CommandError('No reviewed spending policy for this provider/profile. Paid request blocked.')
    if not PRICE_REVIEWED <= now < PRICE_EXPIRES:
        raise CommandError('Pricing review expired or clock invalid. Paid requests are blocked until prices are reviewed.')
    model, effort, ceiling = PROFILES[profile]
    return {'provider': provider, 'profile': profile, 'model': model, 'effort': effort,
            'ceiling_nanos': ceiling, 'max_output_tokens': 2048 if profile=='vision' else MAX_OUTPUT, 'price_version': PRICE_VERSION,
            'rates': MODELS[model], 'price_expires': PRICE_EXPIRES, 'service_tier': 'default'}


def quote_cost(selected_policy, input_tokens):
    if type(input_tokens) is not int or not 1 <= input_tokens <= 16000:
        raise CommandError('Exact input count missing or exceeds the 16,000-token development limit.')
    rates = selected_policy['rates']
    # Assume the most expensive input category for EVERY token; no cache discount assumptions.
    cost = input_tokens * max(rates['input'], rates['cache_write']) + selected_policy['max_output_tokens'] * rates['output']
    if cost > selected_policy['ceiling_nanos']:
        raise CommandError('Worst-case cost exceeds this profile’s request ceiling. Nothing was generated; no automatic escalation.')
    return cost


def settled_usage(result, quote):
    """Return conservative usage-derived cost, not an asserted provider invoice amount."""
    try:
        usage = result['usage']
        incoming, outgoing = usage['input_tokens'], usage['output_tokens']
        if type(incoming) is not int or not 0 <= incoming <= quote['input_tokens']: raise ValueError()
        if type(outgoing) is not int or not 0 <= outgoing <= quote['max_output_tokens']: raise ValueError()
        # Unknown resolved versions require explicit review, not a prefix match.
        if result['model'] != quote['model'] or result['service_tier'] != 'default': raise ValueError()
        if not isinstance(result['output'], list): raise ValueError()
        if not all(item.get('type') in ('message', 'reasoning') for item in result['output']): raise ValueError()
        rates = MODELS[quote['model']]
        cost = incoming * max(rates['input'], rates['cache_write']) + outgoing * rates['output']
        if cost > quote['reserved_nanos']: raise ValueError()
        return incoming, outgoing, cost
    except (ValueError, KeyError, TypeError, AttributeError):
        raise CommandError('Usage/model/tier could not be reconciled against the quote. Reservation retained; paid calls halted for review.') from None


def utc_day(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
