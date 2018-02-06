from setuptools import setup

with open('README') as f:
    long_description = f.read()

setup(
    name='gdax_recurring',
    description='Automates recurring USD deposits and asset allocation for GDAX.',
    long_description=long_description,
    version='1.0.2',
    author='Mark Hudnall',
    author_email='me@markhudnall.com',
    url='https://github.com/landakram/gdax_recurring',
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console', 'License :: OSI Approved :: MIT License',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Financial and Insurance Industry',
        'Topic :: Office/Business :: Financial',
        'Topic :: Office/Business :: Financial :: Investment',
        'Topic :: Security :: Cryptography',
        'Operating System :: OS Independent'
    ],
    py_modules=['cli', 'app'],
    install_requires=[
        'click', 'GDAX>=1.0.0, <2.0.0', 'python-dateutil', 'requests'
    ],
    entry_points='''
        [console_scripts]
        gdax_recurring=cli:run
    ''')
