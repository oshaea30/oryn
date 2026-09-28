"""One admission boundary for paid cognition. UI approval never owns policy or identity."""
import copy
import time
import uuid
from cognition import CommandError
from cognitive_providers import priced_body, count_input, generate_priced, extract
from spending import digest, policy, quote_cost, settled_usage, PRICE_EXPIRES
from usage_ledger import UsageLedger


class PaidGateway:
    def __init__(self, ledger=None, counter=count_input, sender=generate_priced, clock=time.time):
        self.ledger = ledger if ledger is not None else UsageLedger()
        self.counter, self.sender, self.clock = counter, sender, clock
        self.quotes = {}
        # Production auth replaces this server-owned identity, not a browser user_id field.
        self.actor = 'developer'

    def binding(self, selected_policy, body, state, serial, credential_revision):
        return digest({'policy':selected_policy,'body':body,'session':state['session'],
                       'contextToken':state['contextToken'],'serial':serial,'credentials':credential_revision,
                       'actor':self.actor})

    def prepare(self, provider, profile, key, question, state, serial, credential_revision):
        now = int(self.clock())
        chosen = policy(provider, profile, now)
        budget = self.ledger.summary()
        if budget['halted'] or budget['remaining_nanos'] <= 0:
            raise CommandError('Spending is halted or the daily budget is exhausted.')
        self.quotes = {k:v for k,v in self.quotes.items() if v['quote']['expires'] > now}
        if len(self.quotes) >= 100:
            raise CommandError('Too many outstanding quotes. Wait for expiry; nothing generated.')
        body = priced_body(chosen, question, state)
        count = self.counter(key, copy.deepcopy(body))
        cost = quote_cost(chosen, count)
        if cost > budget['remaining_nanos']:
            raise CommandError('This quote exceeds the remaining daily budget. Nothing generated.')
        quote = {'request_id':uuid.uuid4().hex,'actor_id':self.actor,'provider':provider,'profile':profile,
                 'model':chosen['model'],'effort':chosen['effort'],'operation':'intent_interpretation',
                 'fingerprint':self.binding(chosen,body,state,serial,credential_revision),
                 'price_version':chosen['price_version'],'input_tokens':count,'max_output_tokens':chosen['max_output_tokens'],
                 'reserved_nanos':cost,'ceiling_nanos':chosen['ceiling_nanos'],'created':now,
                 'expires':min(now+120, PRICE_EXPIRES)}
        # DB stores only billing metadata + digest; request text/context live in memory for 120 seconds.
        self.ledger.create_quote(quote)
        self.quotes[quote['request_id']] = {'quote':quote,'body':body,
                                          'state':copy.deepcopy(state),'serial':serial}
        return dict(quote, daily_remaining_nanos=budget['remaining_nanos'],
                    input_count_method='provider exact count', tool_cost_nanos=0,
                    note='Conservative maximum, not an invoice. All input reserved at cache-write rate; no discounts assumed.')

    def interpretation_snapshot(self, ident):
        cached = self.quotes.get(ident)
        if cached is None or self.clock() >= cached['quote']['expires']:
            raise CommandError('Quote missing or expired. Prepare a new quote; no paid request sent.')
        # Interpret exactly the already counted facts, not a newer Quest snapshot.
        return cached['serial'], copy.deepcopy(cached['state'])

    def run(self, data, provider, profile, key, question, state, serial, credential_revision):
        ident = data.get('id')
        cached = self.quotes.get(ident)
        if cached is None:
            raise CommandError('Quote missing, expired or from a previous server session. No paid request sent.')
        if data.get('approvePaid') is not True:
            raise CommandError('Approve the quoted maximum cost explicitly.')
        chosen = policy(provider, profile, int(self.clock()))
        body = priced_body(chosen, question, state)
        binding = self.binding(chosen,body,state,serial,credential_revision)
        quote = cached['quote']
        if binding != quote['fingerprint']:
            raise CommandError('Request, selection, profile or credentials changed. Prepare a new quote.')
        self.ledger.reserve(ident,self.actor,binding,data.get('approvedCostNanos'))
        try:
            result = self.sender(key, copy.deepcopy(body))
        except Exception:
            self.ledger.uncertain(ident)
            raise CommandError('Provider result unavailable. Maximum cost remains reserved across restarts; no retry.') from None
        try:
            incoming, outgoing, calculated = settled_usage(result, quote)
        except CommandError:
            self.ledger.uncertain(ident, halt=True)
            raise
        try:
            intent = extract('openai', result)
        except CommandError:
            # Refusal/incomplete generation can still be billed. Count usage even without an action.
            self.ledger.settle(ident,incoming,outgoing,calculated,'invalid_response')
            raise
        self.ledger.settle(ident,incoming,outgoing,calculated,'completed')
        return intent, chosen['model']
