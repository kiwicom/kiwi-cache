from setuptools import find_packages, setup

with open('requirements.in') as f:
    REQUIREMENTS = f.read().splitlines()

with open('test-requirements.in') as f:
    TEST_REQUIREMENTS = f.read().splitlines()

setup(
    name='kiwi-cache',
    version='0.4.1',
    url='https://github.com/kiwicom/kiwi-cache',
    author='Stanislav Komanec',
    author_email='platform@kiwi.com',
    packages=find_packages(),
    install_requires=REQUIREMENTS,
    tests_require=TEST_REQUIREMENTS,
    description="Cache for using Redis with diverse sources.",
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
)
