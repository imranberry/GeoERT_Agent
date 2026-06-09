"""Module 8 — DarZarouk
Computes Dar-Zarouk parameters (T, S, lambda) per layer.
Assesses aquifer contamination vulnerability per Oladapo & Akintorinwa (2007).
"""
import numpy as np
from typing import List, Dict

class DarZarouk:
    """
    Computes Dar-Zarouk parameters for each subsurface layer.
    Assesses aquifer contamination vulnerability based on overburden properties.

    Reference: Oladapo & Akintorinwa (2007), Niwas & Singhal (1981)
    """

    # Vulnerability classification thresholds (Longitudinal Conductance S)
    VULNERABILITY_CLASSES = [
        {'label': 'GOOD',           'S_min': 10.0,  'S_max': 1e9,
         'color': '#228B22', 'icon': '🟢',
         'desc': 'Well protected — Thick, conductive overburden'},
        {'label': 'MODERATE',       'S_min': 1.0,   'S_max': 10.0,
         'color': '#FFA500', 'icon': '🟡',
         'desc': 'Moderately protected — Some risk of contamination'},
        {'label': 'POOR',           'S_min': 0.1,   'S_max': 1.0,
         'color': '#FF6347', 'icon': '🟠',
         'desc': 'Poorly protected — High contamination risk'},
        {'label': 'EXTREMELY POOR', 'S_min': 0.0,   'S_max': 0.1,
         'color': '#DC143C', 'icon': '🔴',
         'desc': 'Extremely vulnerable — Aquifer highly exposed to contaminants'},
    ]

    def compute(self, layers: List[Dict], aquifer_detection: Dict) -> Dict:
        """
        Compute Dar-Zarouk parameters for all layers and assess vulnerability.

        Args:
            layers          : List of classified layers (from TerrainClassifier)
            aquifer_detection: Detection result (from AquiferDetector)

        Returns:
            dict with layer_params, overburden_S, total_T, vulnerability
        """
        layer_params = []

        # Identify primary aquifer layer number
        aquifer_layer_num = None
        if aquifer_detection['aquifer_found']:
            aquifer_layer_num = aquifer_detection['primary_aquifer']['layer_num']

        overburden_S = 0.0  # Protective layer conductance sum
        total_T      = 0.0  # Total transverse resistance

        for layer in layers:
            rho = layer['rho']
            h   = layer.get('thickness') or 20  # half-space default

            T = rho * h    # Transverse resistance
            S = h / rho    # Longitudinal conductance

            is_overburden = (
                aquifer_layer_num is not None and
                layer['layer_num'] < aquifer_layer_num and
                not layer['is_aquifer']
            )

            if is_overburden:
                overburden_S += S

            total_T += T

            layer_params.append({
                'layer_num':     layer['layer_num'],
                'lithology':     layer['name'],
                'rho':           rho,
                'thickness':     h,
                'T':             T,
                'S':             S,
                'is_overburden': is_overburden,
                'is_aquifer':    layer['is_aquifer'],
                'depth_top':     layer['depth_top']
            })

        # Vulnerability assessment
        vulnerability = self._classify_vulnerability(overburden_S)

        # Anisotropy coefficient
        lambda_val = np.sqrt(total_T / (overburden_S + 1e-10)) if overburden_S > 0 else None

        return {
            'layer_params':   layer_params,
            'overburden_S':   overburden_S,
            'total_T':        total_T,
            'vulnerability':  vulnerability,
            'lambda':         lambda_val,
            'aquifer_found':  aquifer_detection['aquifer_found']
        }

    def _classify_vulnerability(self, S: float) -> Dict:
        """Classify overburden protective capacity."""
        for cls in self.VULNERABILITY_CLASSES:
            if cls['S_min'] <= S < cls['S_max']:
                return cls
        return self.VULNERABILITY_CLASSES[-1]

    def print_report(self, dz_result: Dict) -> None:
        print(f"\n{'='*65}")
        print("  DAR-ZAROUK PARAMETERS & CONTAMINATION VULNERABILITY")
        print(f"{'='*65}")
        print(f"  {'#':<4} {'Lithology':<22} {'ρ':>6} {'h(m)':>6} {'T(Ω·m²)':>10} {'S(S)':>10} {'Role':>12}")
        print(f"{'─'*65}")

        for lp in dz_result['layer_params']:
            role = ('AQUIFER'    if lp['is_aquifer'] else
                    'OVERBURDEN' if lp['is_overburden'] else
                    'Substrate')
            print(f"  {lp['layer_num']:<4} {lp['lithology']:<22} "
                  f"{lp['rho']:>6.0f} {lp['thickness']:>6.1f} "
                  f"{lp['T']:>10.1f} {lp['S']:>10.4f} {role:>12}")

        print(f"{'─'*65}")
        print(f"  Total Transverse Resistance (ΣT)  : {dz_result['total_T']:.2f} Ω·m²")
        print(f"  Overburden Longitudinal Cond. (ΣS): {dz_result['overburden_S']:.4f} Siemens")
        if dz_result['lambda']:
            print(f"  Anisotropy Coefficient (λ)        : {dz_result['lambda']:.3f}")

        v = dz_result['vulnerability']
        print(f"{'─'*65}")
        print(f"  {v['icon']} CONTAMINATION VULNERABILITY: {v['label']}")
        print(f"     {v['desc']}")
        print(f"{'='*65}")
