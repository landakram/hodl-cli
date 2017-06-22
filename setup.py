from setuptools import setup

setup(
    name='gdax_recurring',
    version='1.0.0',
    py_modules=['cli', 'app'],
    install_requires=[
        'click', 'GDAX', 'python-dateutil', 'requests'
    ],
    entry_points='''
        [console_scripts]
        gdax_recurring=cli:run
    ''')
