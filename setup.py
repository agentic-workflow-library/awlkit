"""Setup configuration for awlkit."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="awlkit",
    version="0.1.0",
    author="AWLKit Contributors",
    description="Agentic Workflow Library Kit - Tools for workflow language conversion and manipulation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/agentic-workflow-library/awlkit",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "lark>=1.1.0",  # For parsing WDL/CWL
        "pydantic>=2.0",  # For data models
        "networkx>=3.0",  # For workflow graph analysis
        "ruamel.yaml>=0.17",  # For YAML handling (CWL)
        "click>=8.0",  # For CLI tools
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "awlkit=awlkit.cli:main",
        ],
    },
)