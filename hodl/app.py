import os
from decimal import Decimal, ROUND_DOWN

from collections import defaultdict

import dateutil.parser
from dateutil.tz import tzutc

import datetime
import requests
from pprint import pformat as p


class HodlApp:
    def __init__(self,
                 client=None,
                 print_fn=None,
                 dry_run=False,
                 verbose=False):
        self.client = client
        self.print_fn = print_fn
        self.dry_run = dry_run
        self.verbose = verbose
        self.idempotency_fudge_factor = Decimal('0.10')


    def get_payment_method(self, account_type='ach_bank_account', match_substring=''):
        payment_methods = self.client.get_payment_methods()

        for p in payment_methods:
            if p['type'] == account_type and match_substring in p['name']:
                return p

    def get_account_history(self, currency, after=None):
        a = self.get_fiat_account(currency)
        history = self.client.get_account_history(a["id"])
        entries_within_interval = []
        for entry in history:
            created_at = dateutil.parser.parse(entry['created_at'])
            if not after or created_at >= after:
                entries_within_interval.append(entry)
            else:
                break
        return entries_within_interval

    def filter_buys(self, entries):
        for entry in entries:
            amount = Decimal(entry['amount'])
            if entry['type'] in ['match', 'fee'] and amount < 0:
                yield entry

    def group_by_order(self, matches):
        orders_to_matches = defaultdict(list)
        for match in matches:
            details = match['details']
            order_id = details['order_id']
            orders_to_matches[order_id].append(match)
        return orders_to_matches

    def summarize_orders(self, orders_to_matches):
        orders_to_summaries = dict()
        for order, matches in orders_to_matches.items():
            sample_match = list(matches)[0]
            product_id = sample_match['details']['product_id']
            base_curency, quote_currency = product_id.split('-')
            orders_to_summaries[order] = {
                'order_id': order,
                'base_curency': base_curency,
                'quote_currency': quote_currency,
                'amount': self.sum_amounts(matches)
            }
        return orders_to_summaries

    def sum_amounts(self, matches):
        amount = Decimal()
        for match in matches:
            amount += Decimal(match['amount'])
        return amount

    def should_buy(self,
                   currency=None,
                   target_amount=None,
                   allocation_percentages=None,
                   interval=datetime.timedelta(days=15)):
        now = datetime.datetime.now(tzutc())
        entries = self.get_account_history(currency, after=(now - interval))
        buys = self.filter_buys(entries)
        orders = self.group_by_order(buys)
        summaries = self.summarize_orders(orders)

        amounts = self.allocation_amounts(target_amount, allocation_percentages)

        if self.verbose:
            self.print_fn("Comparing orders in last `interval` days to see if we should buy. Considering these orders:")
            self.print_fn(p(orders))
            self.print_fn("Summarized as follows:")
            self.print_fn(p(summaries))
            self.print_fn("Considering these allocation amounts:")
            self.print_fn(p(amounts))
        for id, order in summaries.items():
            for base_currency, amount_in_quote_currency in amounts.items():
                if self.verbose:
                    self.print_fn(abs(-order['amount'] - amount_in_quote_currency))
                    self.print_fn(self.idempotency_fudge_factor)

                if (order['base_curency'] == base_currency and
                    abs(-order['amount'] - amount_in_quote_currency) <= self.idempotency_fudge_factor):
                    return False
        return True

    def get_all_deposits(self, currency):
        a = self.get_fiat_account(currency)
        r = requests.get(self.client.url + '/accounts/{}/transfers'.format(a['id']),
                         auth=self.client.auth)
        return r.json()

    def should_create_deposit(self, deposits, target_amount=None, interval=datetime.timedelta(days=15)):
        for d in deposits:
            created_at = dateutil.parser.parse(d['created_at'])
            canceled_at = d['canceled_at']
            completed_at = dateutil.parser.parse(d['completed_at']) if d[
                'completed_at'] else None

            now = datetime.datetime.now(tzutc())
            if (created_at > (now - interval) and
                abs(Decimal(d['amount']) - target_amount) <= self.idempotency_fudge_factor):
                if self.verbose:
                    self.print_fn("Found recent deposit: \n{}".format(p(d)))
                return False
        return True


    def get_fiat_account(self, currency):
        accounts = self.client.get_accounts()
        for a in accounts:
            if a['currency'] == currency:
                return a


    def allocation_amounts(self, amount, allocation_percentages):
        asset_allocation = dict()
        for currency, percentage in allocation_percentages.items():
            allocation = amount * Decimal(percentage)
            asset_allocation[currency] = allocation
        return asset_allocation


    def get_available_to_trade(self, currency):
        account = self.get_fiat_account(currency)
        return Decimal(account['available'])


    def buy(self, base_currency, quote_currency, amount_in_quote_currency):
        pair = '{}-{}'.format(base_currency, quote_currency)
        funds = amount_in_quote_currency.quantize(Decimal('.01'), rounding=ROUND_DOWN)
        buy_params = dict(
            product_id=pair, order_type='market', funds=str(funds))
        if self.dry_run:
            self.print_fn('** Dry run mode **')
            self.print_fn('I would have bought {} {} worth of {}'.format(
                funds, quote_currency, base_currency
            ))
            self.print_fn(buy_params)
            return dict(dry_run=True, **buy_params)
        else:
            return self.client.buy(**buy_params)


    def allocate_fiat(self,
                      quote_currency,
                      allocation_percentages=dict(),
                      buy_amount=Decimal('100')):
        available = self.get_available_to_trade(quote_currency)
        buys = list()
        if available >= buy_amount:
            amounts = self.allocation_amounts(buy_amount, allocation_percentages)
            for base_currency, amount_in_quote_currency in amounts.items():
                buys.append(self.buy(base_currency, quote_currency, amount_in_quote_currency))
        else:
            self.print_fn(
                "Not allocating because available ${} is less than buy_amount ${}".format(
                    available,
                    buy_amount
                )
            )
        return buys


    def deposit(self, amount, payment_method):
        funds = amount.quantize(Decimal('.01'), rounding=ROUND_DOWN)
        if self.dry_run:
            self.print_fn('** Dry run mode **')
            self.print_fn('I would have deposited {} {} using {}'.format(funds, payment_method['currency'], payment_method['name']))
        else:
            return self.client.deposit(
                amount=str(funds),
                currency=payment_method['currency'],
                payment_method_id=payment_method['id']
            )


    def run(self,
            deposit_account,
            deposit_account_type,
            deposit_amount,
            interval,
            buy_amount,
            asset_allocation):
        if self.dry_run:
            self.print_fn("⚠️  Dry run mode ⚠️  ")

        payment_method = self.get_payment_method(
            account_type=deposit_account_type,
            match_substring=deposit_account
        )
        if not payment_method:
            raise Exception("⚠️  No deposit account found with type {} and name {}.".format(deposit_account_type, deposit_account))

        fiat_currency = payment_method['currency']
        prev_deposits = self.get_all_deposits(fiat_currency)
        if self.verbose:
            self.print_fn(p(prev_deposits))

        self.print_fn('Checking whether to deposit...')
        if self.should_create_deposit(prev_deposits, target_amount=deposit_amount, interval=interval):
            self.print_fn('No deposit for {} {} in {}. Creating deposit for {} {}.'.format(
                deposit_amount, fiat_currency,
                interval,
                deposit_amount, fiat_currency))
            self.print_fn(p(self.deposit(deposit_amount, payment_method)))
        else:
            self.print_fn('Skipped deposit.')

        self.print_fn('Checking whether to allocate...')
        if self.should_buy(currency=fiat_currency,
                           target_amount=buy_amount,
                           allocation_percentages=asset_allocation,
                           interval=interval):
            allocations = self.allocate_fiat(
                fiat_currency,
                buy_amount=buy_amount,
                allocation_percentages=asset_allocation
            )
            self.print_fn(p(allocations))
            self.print_fn('Done.')
        else:
            self.print_fn('Skipped allocations.')
