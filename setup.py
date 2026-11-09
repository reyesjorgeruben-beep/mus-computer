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
        "review": [
            "ruff==0.17.4",
            "mypy==2.4.1",
            "pre-commit==4.6.2",
            "types-setuptools==84.2.0.20261104",
            "plotly-stubs==0.0.6",
            "plotly>=5,<8",
        ],
        "tables": ["numpy==1.26.4"],
    },
    entry_points={"console_scripts": ["mus-computer=mus_computer.cli:main"]},
)
