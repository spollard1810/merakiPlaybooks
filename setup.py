from setuptools import setup, find_packages

setup(
    name="meraki_auditor",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "meraki>=1.34.0",
        "pyyaml>=6.0",
        "pandas>=1.5.0",
        "tk",
    ],
    python_requires=">=3.7",
) 