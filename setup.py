from setuptools import setup, find_packages

version = '0.0.1a4'

long_description = (
    open('README.rst').read()
    + '\n' +
    'Contributors\n'
    '============\n'
    + '\n' +
    open('CONTRIBUTORS.txt').read()
    + '\n' +
    open('CHANGES.txt').read()
    + '\n')

requires = ['colander']

setup(name='bbe.cielo',
      version=version,
      description="A Cielo client.",
      long_description=long_description,
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='',
      author='',
      author_email='',
      url='https://github.com/bambae/bbe.cielo',
      license='bsd',
      packages=find_packages(),
      namespace_packages=['bbe'],
      include_package_data=True,
      zip_safe=False,
      install_requires=['setuptools'] + requires,
      test_suite='bbe.cielo',
      test_require=requires,
      )
