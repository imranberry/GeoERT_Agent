"""
GeoERT Agent — setup.py
Makes the package pip-installable: pip install -e .
"""

from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt") as f:
    # Strip comments and blank lines
    install_requires = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#") and not line.startswith("-")
    ]

setup(
    name                          = "geoert-agent",
    version                       = "1.0.0",
    author                        = "Malik Oluwatobiloba Imran",
    description                   = "AI-powered ERT geophysical interpretation: aquifer detection, Dar-Zarouk analysis & contamination risk",
    long_description              = long_description,
    long_description_content_type = "text/markdown",
    url                           = "https://github.com/yourusername/geoert-agent",
    packages                      = find_packages(exclude=["tests*", "docs*"]),
    python_requires               = ">=3.10",
    install_requires              = install_requires,
    entry_points={
        "console_scripts": [
            "geoert=run:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: GIS",
        "Intended Audience :: Science/Research",
    ],
    keywords=[
        "geophysics", "ERT", "resistivity", "aquifer",
        "hydrogeology", "VES", "inversion", "dar-zarouk"
    ],
)
