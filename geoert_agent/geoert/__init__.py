"""
GeoERT Agent — ERT Geophysical Interpretation Package
======================================================
A complete pipeline for Vertical Electrical Sounding (VES) interpretation:
  apparent resistivity → curve type → inversion → geology → aquifer → Dar-Zarouk → plots

Supported arrays : Schlumberger · Wenner · Dipole-Dipole
Terrain types    : Sedimentary Basin · Basement Complex
Deployment       : Jupyter Notebook · Telegram Bot · FastAPI

Author : Malik Oluwatobiloba Imran (Codar Data Science Program)
"""

from .ert_calculator import ERTCalculator
from .curve_type import CurveTypeClassifier
from .inversion import Inversion1D
from .terrain_classifier import TerrainClassifier
from .aquifer_detector import AquiferDetector
from .dar_zarouk import DarZarouk
from .visualizer import Visualizer
from .sample_data import SampleDataGenerator
from .agent import GeoERTAgent

__all__ = [
    "ERTCalculator",
    "CurveTypeClassifier",
    "Inversion1D",
    "TerrainClassifier",
    "AquiferDetector",
    "DarZarouk",
    "Visualizer",
    "SampleDataGenerator",
    "GeoERTAgent",
]

__version__ = "1.0.0"
__author__  = "Malik Oluwatobiloba Imran"
