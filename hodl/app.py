import os
from decimal import Decimal, ROUND_DOWN

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


    def get_payment_method(self, account_type='ach_bank_account', match_substring=''):
        payment_methods = self.client.get_payment_methods()

        for p in payment_methods:
            if p['type'] == account_type and match_substring in p['name']:
                return p


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
            if created_at > (now - interval) and d['amount'] == target_amount:
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
            product_id=pair, type='market', side='buy', funds=str(funds))
        if self.dry_run:
            self.print_fn('dry_run')
            self.print_fn(buy_params)
            return dict(dry_run=True, **buy_params)
        else:
            return self.client.buy(**buy_params)


    def allocate_fiat(self,
                      quote_currency,
                      allocation_percentages=dict(),
                      minimum_available_to_trade=Decimal('100')):
        available = self.get_available_to_trade(quote_currency)
        buys = list()
        if available >= minimum_available_to_trade:
            amounts = self.allocation_amounts(available, allocation_percentages)
            for base_currency, amount_in_quote_currency in amounts.items():
                buys.append(self.buy(base_currency, quote_currency, amount_in_quote_currency))
        elif self.verbose:
            self.print_fn(
                "Not allocating because available ${} is less than minimum_available_to_trade ${}".format(
                    available,
                    minimum_available_to_trade
                )
            )
        return buys


    def deposit(self, amount, payment_method):
        if self.dry_run:
            self.print_fn("dry_run")
            self.print_fn("Deposit params: \n{} \n{}".format(p(amount), p(payment_method)))
        else:
            return self.client.deposit(
                amount=amount,
                currency=payment_method['currency'],
                payment_method_id=payment_method['id']
            )


    def run(self,
            deposit_account,
            deposit_account_type,
            deposit_amount,
            deposit_interval,
            min_available_to_trade,
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
        if self.should_create_deposit(prev_deposits, target_amount=deposit_amount, interval=deposit_interval):
            self.print_fn('No deposit for ${} in {}. Creating deposit for ${}.'.format(
                deposit_amount,
                deposit_interval, deposit_amount))
            self.print_fn(p(self.deposit(deposit_amount, payment_method)))
        else:
            self.print_fn('Skipped deposit.')

        self.print_fn('Checking whether to allocate...')
        allocations = self.allocate_fiat(
            fiat_currency,
            minimum_available_to_trade=min_available_to_trade,
            allocation_percentages=asset_allocation
        )
        if not allocations:
            self.print_fn('Skipped allocations.')
        else:
            self.print_fn(p(allocations))
            self.print_fn('Done.')
