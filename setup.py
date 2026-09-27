"""Editable-install fallback for older pip/setuptools in local Python 3.10."""

from setuptools import find_packages, setup

setup(
    name="mus-computer",
    version="0.1.0",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages("src"),
    package_data={"mus_computer.probabilities": ["data/*.pkl"]},
    include_package_data=True,
    install_requires=[],
    extras_require={
        "dev": ["pytest==9.0.2", "numpy==1.26.4"],
        "tables": ["numpy==1.26.4"],
    },
    entry_points={"console_scripts": ["mus-computer=mus_computer.cli:main"]},
)
