"""Module 7 — AquiferDetector
Detects and characterises aquifer zones from classified layer model.
Provides yield potential estimate and recommended borehole depth.
"""
import numpy as np
from typing import List, Dict

class AquiferDetector:
    """
    Detects and characterises aquifer zones from classified layer model.
    Provides yield potential estimate and recommended borehole depth.
    """

    # Minimum thickness to be considered a viable aquifer (m)
    MIN_AQUIFER_THICKNESS = 3.0

    # Resistivity contrast ratio: aquifer must be >> confining layer
    MIN_CONTRAST_RATIO = 2.0

    YIELD_CLASSIFICATION = [
        {'label': 'Very High',  'min_rho': 400, 'min_thick': 15,
         'desc': 'Excellent — High-capacity borehole expected'},
        {'label': 'High',       'min_rho': 200, 'min_thick': 8,
         'desc': 'Good — Productive borehole likely'},
        {'label': 'Moderate',   'min_rho': 80,  'min_thick': 4,
         'desc': 'Fair — Borehole may be viable'},
        {'label': 'Low',        'min_rho': 10,  'min_thick': 2,
         'desc': 'Poor — Limited yield expected'},
    ]

    def detect(self, layers: List[Dict], terrain: str) -> Dict:
        """
        Detect aquifer zones and rank them.

        Returns dict with aquifer_zones, primary_aquifer, recommendation
        """
        aquifer_zones = []

        for i, layer in enumerate(layers):
            if not layer['is_aquifer']:
                continue

            thickness = layer.get('thickness', 0)
            if thickness is None:
                thickness = 20  # half-space estimate

            if thickness < self.MIN_AQUIFER_THICKNESS:
                continue

            # Compute yield potential
            yield_info = self._estimate_yield(
                layer['rho'], thickness, terrain
            )

            # Check resistivity contrast with overlying layer
            contrast = 1.0
            if i > 0:
                prev_rho = layers[i-1]['rho']
                contrast = layer['rho'] / prev_rho if prev_rho > 0 else 1.0

            aquifer_zones.append({
                'layer_num':      layer['layer_num'],
                'lithology':      layer['name'],
                'depth_top':      layer['depth_top'],
                'depth_bottom':   (layer['depth_top'] + thickness) if layer.get('depth_bot') is None else layer['depth_bot'],
                'thickness':      thickness,
                'resistivity':    layer['rho'],
                'yield_label':    yield_info['label'],
                'yield_desc':     yield_info['desc'],
                'contrast_ratio': round(contrast, 2),
                'score':          yield_info['score'],
                'color':          layer['color']
            })

        # Sort by score
        aquifer_zones.sort(key=lambda x: x['score'], reverse=True)

        if not aquifer_zones:
            return {
                'aquifer_found':  False,
                'aquifer_zones':  [],
                'primary_aquifer': None,
                'recommendation': (
                    '⚠️  No viable aquifer detected in the survey depth range.\n'
                    '   Consider deeper VES or alternative siting.'
                )
            }

        primary = aquifer_zones[0]
        depth_bot = primary['depth_bottom'] if primary['depth_bottom'] is not None else primary['depth_top'] + primary['thickness']
        rec_depth = depth_bot + 5  # 5m below aquifer base

        return {
            'aquifer_found':   True,
            'aquifer_zones':   aquifer_zones,
            'primary_aquifer': primary,
            'recommendation':  (
                f"✅ Primary aquifer: {primary['lithology']} at "
                f"{primary['depth_top']:.1f}–{depth_bot:.1f}m depth.\n"
                f"   Yield potential: {primary['yield_label']} — {primary['yield_desc']}.\n"
                f"   Recommended borehole depth: ≥ {rec_depth:.0f}m."
            )
        }

    def _estimate_yield(self, rho: float, thickness: float,
                         terrain: str) -> Dict:
        """Estimate yield potential from resistivity and thickness."""
        # Score = weighted combination of rho and thickness
        rho_score   = np.log1p(rho) / np.log1p(5000)
        thick_score = np.log1p(thickness) / np.log1p(50)
        score = 0.6 * rho_score + 0.4 * thick_score

        for cls in self.YIELD_CLASSIFICATION:
            if rho >= cls['min_rho'] and thickness >= cls['min_thick']:
                return {'label': cls['label'], 'desc': cls['desc'], 'score': score}

        return {'label': 'Low', 'desc': 'Limited yield', 'score': score * 0.3}

    def print_report(self, detection: Dict) -> None:
        print(f"\n{'='*65}")
        print("  AQUIFER DETECTION REPORT")
        print(f"{'='*65}")

        if not detection['aquifer_found']:
            print(f"  {detection['recommendation']}")
            return

        for i, az in enumerate(detection['aquifer_zones']):
            tag = '★ PRIMARY' if i == 0 else f'  Zone {i+1}'
            print(f"  {tag}: {az['lithology']}")
            d_bot = az["depth_bottom"] if az["depth_bottom"] is not None else az["depth_top"] + az["thickness"]
            print(f"     Depth    : {az['depth_top']:.1f}m – {d_bot:.1f}m")
            print(f"     Thickness: {az['thickness']:.1f}m")
            print(f"     ρ (Ω·m)  : {az['resistivity']:.1f}")
            print(f"     Yield    : {az['yield_label']} — {az['yield_desc']}")
            print(f"     Contrast : {az['contrast_ratio']:.2f}x overlying layer")
            print()

        print(f"  RECOMMENDATION:")
        print(f"  {detection['recommendation']}")
        print(f"{'='*65}")
