import setuptools

with open('Readme.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name = 'AntPool',
    version = '0.12',
    author = 'Charles Lai',
    author_email = '',
    description = 'AntPool',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url = 'https://github.com/wolf71/AntPool',
    packages = ['AntPool'],   #setuptools.find_packages(),
    install_requires=['tornado==6.1'],
    entry_points={
        'console_scripts': [
            'antpoolsrv = AntPool.antpoolSrv:main',
            'antpoolclient = AntPool.antpoolClient:main'
        ],
    },
    classifiers=(
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ),
)