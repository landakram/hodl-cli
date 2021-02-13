import datetime
import os

from decimal import Decimal

import click
import cbpro

from hodl_cli.app import HodlApp


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option(
    '--deposit-account',
    '-n',
    default='',
    help='Name string used to filter multiple bank accounts. If not specified, the first account found with `deposit-account-type` is used')
@click.option(
    '--deposit-account-type',
    '-t',
    default='ach_bank_account',
    help='Account type used in conjunction with `deposit-account` to find an account from which to deposit fiat')
@click.option(
    '--deposit-amount',
    '-d',
    default=Decimal('100.00'),
    type=Decimal,
    help='Amount to deposit every `interval` days')
@click.option(
    '--interval',
    '-i',
    type=int,
    default='15',
    help='Interval in days after which a deposit and/or buy should be made')
@click.option(
    '--buy-amount',
    '-b',
    default=Decimal('100.00'),
    type=Decimal,
    help='The amount of fiat to allocate every `interval` days'
)
@click.option(
    '--allocation-percentage',
    '-a',
    type=(str, Decimal),
    multiple=True,
    help='A currency and the percentage of available funds that should be allocated to it. This option may be provided multiple times for different currencies and the total percentage should add up to 1. If the total percentage is less than one, the remainder will be left as fiat. \n\nExample: -a ETH 0.25 -a BTC 0.25 -a LTC 0.5'
)
@click.option(
    '--dry-run',
    default=False,
    is_flag=True,
    type=bool,
    help='When present, print what we would have done but don\'t actually deposit or buy anything'
)
@click.option(
    '--verbose',
    '-v',
    default=False,
    is_flag=True,
    type=bool,
    help='When present, print debug logs.')
def run(deposit_account,
        deposit_account_type,
        deposit_amount,
        interval,
        buy_amount,
        allocation_percentage,
        dry_run,
        verbose):
    """
    Dollar-cost averaging for crypto on the command line using Coinbase Pro.

    When run, hodl-cli will check whether a deposit needs to be made and, if so, initiate
    the deposit using a linked bank account.

    Then, if there is enough available fiat in the Pro account, hodl-cli will buy currencies
    using the specified fiat amount, given a user-specified asset allocation. Currencies
    are traded at market price at the time the script is run.

    hodl-cli is meant to be run as a cron. The cron can be run at any interval
    less than the `interval` -- I recommend daily.
    The script will ensure that deposits and buys are only made every `interval`
    days irrespective of how often it is run. This is done by searching account 
    history in the past `interval` days and ensuring that no deposit or buy for a given
    amount has been executed.

    hodl-cli does *not* protect against concurrency issues. Please make sure that only one
    instance of hodl-cli is running at a time to prevent duplicate deposits and buys (PRs welcome).

    In addition to the CLI options, a few environment variables must be present:

    \b
        COINBASE_PRO_API_KEY
        COINBASE_PRO_API_SECRET
        COINBASE_PRO_PASSPHRASE

    Installation:

    \b
        pip install hodl-cli

    Example usage:

    \b
        export COINBASE_PRO_API_KEY=<your_api_key>
        export COINBASE_PRO_API_SECRET=<your_api_secret>
        export COINBASE_PRO_PASSPHRASE=<your_passphrase>
        hodl-cli -i 15 -d 100.00 -b 95.00 -a LTC 0.10 -a ETH 0.60 -a BTC 0.30

    Explanation:

        The above invocation will deposit $100.00 every 15 days. In addition, if the Pro account 
        has $95.00 available to trade, $95.00 will used to buy other currencies as follows:

    \b
        10% will be used to buy LTC
        60% will be used to buy ETH
        30% will be used to buy BTC
    """
    required_env_variables = ['COINBASE_PRO_API_KEY', 'COINBASE_PRO_API_SECRET',
                              'COINBASE_PRO_PASSPHRASE']
    for v in required_env_variables:
        if v not in os.environ:
            raise click.ClickException(
                '⚠️  {} must be specified in the environment.'.format(v))

    interval = datetime.timedelta(days=interval)
    buy_amount = Decimal(buy_amount)
    allocation_percentage = dict(allocation_percentage)

    def print_function(message):
        click.echo('{}: {}'.format(datetime.datetime.now(), message))

    client = cbpro.AuthenticatedClient(
        os.environ.get('COINBASE_PRO_API_KEY'),
        os.environ.get('COINBASE_PRO_API_SECRET'),
        os.environ.get('COINBASE_PRO_PASSPHRASE')
    )

    app = HodlApp(client=client, print_fn=print_function, dry_run=dry_run, verbose=verbose)
    app.run(
        deposit_account,
        deposit_account_type,
        deposit_amount,
        interval,
        buy_amount,
        allocation_percentage
    )

