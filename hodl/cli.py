import datetime
import os

from decimal import Decimal

import click
import cbpro

from hodl.app import HodlApp


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
    help='Amount to deposit every `deposit-interval` days')
@click.option(
    '--deposit-interval',
    '-i',
    type=int,
    default='15',
    help='Interval in days after which a deposit should be made')
@click.option(
    '--min-available-to-trade',
    '-m',
    default=Decimal('100.00'),
    type=Decimal,
    help='The minimum available balance in fiat that, when met, will result in an allocation'
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
        deposit_interval,
        min_available_to_trade,
        allocation_percentage,
        dry_run,
        verbose):
    """
    Dollar-cost averaging for crypto on the command line using Coinbase Pro.

    When run, hodl will check whether a deposit needs to be made and, if so, initiate
    the deposit using a linked bank account.

    Then, if there is enough available fiat in the Pro account, it will buy currencies
    using all of the available fiat, given a user-specified asset allocation. Currencies
    are traded at market price at the time the script is run.

    hodl is meant to be run as a cron. The cron can be run at any interval
    less than the `deposit-interval` -- I recommend daily.
    The script will ensure that deposits are only made every `deposit-interval`
    irrespective of how often it is run. Please make sure that only one
    instance of hodl is running at a time to prevent duplicate
    deposits.

    In addition to the CLI options, a few environment variables must be present:

    \b
        COINBASE_PRO_API_KEY
        COINBASE_PRO_API_SECRET
        COINBASE_PRO_PASSPHRASE

    Installation:

    \b
        pip install hodl

    Example usage:

    \b
        export COINBASE_PRO_API_KEY=<your_api_key>
        export COINBASE_PRO_API_SECRET=<your_api_secret>
        export COINBASE_PRO_PASSPHRASE=<your_passphrase>
        hodl -d 100.00 -i 15 -m 50.00 -a LTC 0.5 -a ETH 0.25 -a BTC 0.25

    Explanation:

        The above invocation will deposit $100.00 every 15 days. In addition, if the Pro account has at least $50.00 available to trade, all of the available fiat will be used to buy other currencies as follows:

    \b
        50% will be used to buy LTC
        25% will be used to buy ETH
        25% will be used to buy BTC
    """
    required_env_variables = ['COINBASE_PRO_API_KEY', 'COINBASE_PRO_API_SECRET',
                              'COINBASE_PRO_PASSPHRASE']
    for v in required_env_variables:
        if v not in os.environ:
            raise click.ClickException(
                '⚠️  {} must be specified in the environment.'.format(v))

    deposit_interval = datetime.timedelta(days=deposit_interval)
    min_available_to_trade = Decimal(min_available_to_trade)
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
        deposit_interval,
        min_available_to_trade,
        allocation_percentage
    )
