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
                 print_fn=None):
        self.client = client
        self.print_fn = print_fn

    def get_bank_id(self):
        account_type = 'ach_bank_account'
        payment_methods = self.client.get_payment_methods()

        for p in payment_methods:
            if p['type'] == account_type:
                return p['id']


    def get_completed_deposits(self):
        a = self.get_usd_account()
        history = self.client.get_account_history(a['id'])[0]
        for entry in history:
            if entry['type'] == 'transfer' and entry['details'][
                    'transfer_type'] == 'deposit':
                yield entry


    def get_all_deposits(self):
        a = self.get_usd_account()
        r = requests.get(self.client.url + '/accounts/{}/transfers'.format(a['id']),
                         auth=self.client.auth)
        return r.json()


    def should_create_deposit(self, deposits, interval=datetime.timedelta(days=15)):
        for d in deposits:
            created_at = dateutil.parser.parse(d['created_at'])
            canceled_at = d['canceled_at']
            completed_at = dateutil.parser.parse(d['completed_at']) if d[
                'completed_at'] else None

            now = datetime.datetime.now(tzutc())
            if created_at > (now - interval):
                return False
        return True


    def get_usd_account(self):
        accounts = self.client.get_accounts()
        for a in accounts:
            if a['currency'] == 'USD':
                return a


    def allocation_amounts(self, amount, allocation_percentages):
        asset_allocation = dict()
        for currency, percentage in allocation_percentages.items():
            allocation = amount * Decimal(percentage)
            asset_allocation[currency] = allocation
        return asset_allocation


    def get_available_to_trade(self):
        account = self.get_usd_account()
        return Decimal(account['available'])


    def buy(self, currency, amount_in_usd, dry_run=False):
        pair = '{}-USD'.format(currency)
        funds = amount_in_usd.quantize(Decimal('.01'), rounding=ROUND_DOWN)
        buy_params = dict(
            product_id=pair, type='market', side='buy', funds=str(funds))
        if dry_run:
            self.print_fn('dry_run')
            self.print_fn(buy_params)
        else:
            return self.client.buy(**buy_params)


    def allocate_usd(self,
                     dry_run=False,
                     allocation_percentages=dict(),
                     minimum_available_to_trade=Decimal('100')):
        available = self.get_available_to_trade()
        buys = list()
        if available >= minimum_available_to_trade:
            amounts = self.allocation_amounts(available, allocation_percentages)
            for currency, amount_in_usd in amounts.items():
                buys.append(
                    self.buy(currency, amount_in_usd, client=client, dry_run=dry_run))
        return buys


    def deposit(self, amount):
        payment_id = self.get_bank_id()
        return self.client.deposit(
            amount=amount,
            currency='USD',
            payment_method_id=payment_id
        )


    def run(self, deposit_amount, deposit_interval, min_available_to_trade, asset_allocation):
        prev_deposits = self.get_all_deposits()
        self.print_fn('Checking whether to deposit...')
        if self.should_create_deposit(prev_deposits, interval=deposit_interval):
            self.print_fn('No deposit in {}. Creating deposit for ${}.'.format(
                deposit_interval, deposit_amount))
            self.print_fn(p(deposit(deposit_amount)))
        else:
            self.print_fn('Skipped deposit.')

        self.print_fn('Checking whether to allocate...')
        allocations = self.allocate_usd(
            minimum_available_to_trade=min_available_to_trade,
            allocation_percentages=asset_allocation)
        if not allocations:
            self.print_fn('Skipped allocations.')
        else:
            self.print_fn(p(allocations))
            self.print_fn('Done.')
