"""Module 10 — GeoERTAgent
Full ERT interpretation pipeline orchestrator.
Chains all modules into a single .run() call.
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict

from .ert_calculator import ERTCalculator
from .curve_type import CurveTypeClassifier
from .inversion import Inversion1D
from .terrain_classifier import TerrainClassifier
from .aquifer_detector import AquiferDetector
from .dar_zarouk import DarZarouk
from .visualizer import Visualizer

class GeoERTAgent:
    """
    Full ERT Interpretation Pipeline.

    Usage:
        agent = GeoERTAgent()
        result = agent.run(
            df         = your_dataframe,
            array_type = 'schlumberger',
            terrain    = 'sedimentary',
            site_name  = 'Kano Basin'
        )
    """

    def __init__(self):
        self.calc     = ERTCalculator()
        self.cta      = CurveTypeClassifier()
        self.inv      = Inversion1D(n_layers=4)
        self.terrain  = TerrainClassifier()
        self.aquifer  = AquiferDetector()
        self.dz       = DarZarouk()
        

    def run(self, df: pd.DataFrame, array_type: str,
             terrain: str, site_name: str = 'Survey Site',
             save_dir: str = '.') -> Dict:
        """
        Full pipeline: raw data → complete geological report.

        Args:
            df         : Raw survey DataFrame
            array_type : 'schlumberger', 'wenner', or 'dipole_dipole'
            terrain    : 'sedimentary' or 'basement'
            site_name  : Name for plot titles
            save_dir   : Directory to save output images

        Returns:
            Full result dict with all outputs
        """
        print(f"\n{'█'*55}")
        print(f"  🌍 GeoERT AGENT — {site_name}")
        print(f"  Array: {array_type.upper()} | Terrain: {terrain.upper()}")
        print(f"{'█'*55}\n")

        # ── Step 1: Compute apparent resistivity
        print('  [1/7] Computing apparent resistivity...')
        ert_df = self.calc.compute(df, array_type)
        print(f'        ρₐ range: {ert_df["rho_a"].min():.1f} – {ert_df["rho_a"].max():.1f} Ω·m')

        # ── Step 2: 1D Inversion
        print('  [2/7] Running 1D inversion...')
        inv_result = self.inv.invert(ert_df, terrain=terrain)
        self.inv.print_model(inv_result)

        # ── Step 2b: Curve type analysis (needs both apparent + inverted)
        print('  [2b/7] Classifying VES curve type...')
        apparent_type = self.cta.classify_from_apparent(ert_df['spacing'].values, ert_df['rho_a'].values)
        layer_type    = self.cta.classify_from_layers(inv_result['resistivities'])
        self.cta.print_report(apparent_type, layer_type)
        print(f'        Curve type: {apparent_type["curve_type"]}')

        # ── Step 3: Layer classification
        print('  [3/7] Classifying geological layers...')
        layers = self.terrain.classify_all_layers(inv_result, terrain)
        self.terrain.print_layers(layers)

        # ── Step 4: Aquifer detection
        print('  [4/7] Detecting aquifer zones...')
        aquifer_result = self.aquifer.detect(layers, terrain)
        self.aquifer.print_report(aquifer_result)

        # ── Step 5: Dar-Zarouk
        print('  [5/7] Computing Dar-Zarouk parameters...')
        dz_result = self.dz.compute(layers, aquifer_result)
        self.dz.print_report(dz_result)

        # ── Step 6: Visualizations
        print('  [6/7] Generating visualizations...')
        viz = Visualizer(site_name=site_name)

        os.makedirs(save_dir, exist_ok=True)
        dashboard_path = os.path.join(save_dir, 'dashboard.png')
        borehole_path  = os.path.join(save_dir, 'borehole_3d.png')

        loglog_path = os.path.join(save_dir, 'loglog_annotated.png')
        fig_loglog = self.cta.plot_curve_diagnosis(
            apparent_type, layer_type, inv_result,
            site_name=site_name
        )
        fig_loglog.savefig(loglog_path, bbox_inches='tight', dpi=150)
        import matplotlib.pyplot as _plt; _plt.close(fig_loglog)

        fig_dash = viz.plot_dashboard(
            inv_result, layers, aquifer_result, dz_result,
            array_type=array_type,
            save_path=dashboard_path
        )

        fig_3d = viz.plot_3d_borehole(
            layers, aquifer_result,
            save_path=borehole_path
        )

        print(f'\n  ✅ Complete. Outputs saved to: {save_dir}')

        return {
            'apparent_curve_type': apparent_type,
            'layer_curve_type':    layer_type,
            'ert_df':         ert_df,
            'inv_result':     inv_result,
            'layers':         layers,
            'aquifer_result': aquifer_result,
            'dz_result':      dz_result,
            'apparent_curve_type': apparent_type,
            'layer_curve_type':    layer_type,
            'loglog_path':    loglog_path,
            'dashboard_path': dashboard_path,
            'borehole_path':  borehole_path,
            'figures':        [fig_dash, fig_3d]
        }

    def from_csv(self, filepath: str, array_type: str,
                  terrain: str, site_name: str = 'Survey Site',
                  save_dir: str = '.') -> Dict:
        """Load CSV file and run full pipeline."""
        df = pd.read_csv(filepath)
        print(f'  Loaded {filepath}: {df.shape[0]} readings')
        return self.run(df, array_type, terrain, site_name, save_dir)
