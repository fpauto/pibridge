"""
Setup configuration for PiBridge
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name='pibridge',
    version='1.3.0',
    description='WiFi management tool for Raspberry Pi',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='PiBridge Team',
    packages=find_packages(),
    install_requires=[
        'PyYAML>=6.0',
        'python-dateutil>=2.8.0',
    ],
    entry_points={
        'console_scripts': [
            'pibridge=pibridge.cli:main',
        ],
    },
    python_requires='>=3.9',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Networking',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)