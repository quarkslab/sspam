from setuptools import setup


with open('README.rst') as f:
    readme = f.read()

setup(
    name='sspam',
    description='Symbolic Simplification with PAttern Matching',
    long_description=readme,
    packages=["sspam"]
)
