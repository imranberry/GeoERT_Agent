"""Module 6 — TerrainClassifier
Depth-aware geological layer classifier.
Enforces geological realism: topsoil in first 5m, depth gates on all entries.
"""
import numpy as np
from typing import List, Dict

class TerrainClassifier:
    """
    Classifies subsurface layers by resistivity AND depth context.

    Depth Rules enforced:
      - 0 to TOPSOIL_DEPTH_THRESHOLD (default 5m): ALWAYS topsoil/overburden
      - Below threshold: full catalog match filtered by allowed depth range
      - Each catalog entry has depth_min / depth_max guards
        (e.g. Fractured Basement cannot appear at 2m depth)

    References: Telford et al. (1990), Oladapo & Akintorinwa (2007)
    """

    TOPSOIL_DEPTH_THRESHOLD = 5.0  # metres — layers shallower than this = overburden

    # ── SEDIMENTARY CATALOG
    # Each entry: rho_min, rho_max (Ohm.m), depth_min, depth_max (m), priority
    # depth_min/max = None means no depth restriction
    SEDIMENTARY = [
        # Zone 0-5m: topsoil entries (depth_max=5)
        {'name': 'Dry Topsoil',       'rho_min': 100,  'rho_max': 600,    'depth_min': 0,    'depth_max': 5,    'color': '#8B4513', 'aquifer': False, 'priority': 1},
        {'name': 'Moist Topsoil',     'rho_min': 20,   'rho_max': 100,    'depth_min': 0,    'depth_max': 5,    'color': '#A0522D', 'aquifer': False, 'priority': 1},
        {'name': 'Humic Topsoil',     'rho_min': 5,    'rho_max': 20,     'depth_min': 0,    'depth_max': 5,    'color': '#6B3A2A', 'aquifer': False, 'priority': 1},
        # Transitional zone 2m+
        {'name': 'Clay / Shale',      'rho_min': 1,    'rho_max': 30,     'depth_min': 2,    'depth_max': None, 'color': '#708090', 'aquifer': False, 'priority': 2},
        {'name': 'Sandy Clay',        'rho_min': 30,   'rho_max': 100,    'depth_min': 3,    'depth_max': None, 'color': '#DAA520', 'aquifer': False, 'priority': 2},
        {'name': 'Shale / Mudstone',  'rho_min': 1,    'rho_max': 50,     'depth_min': 5,    'depth_max': None, 'color': '#556B2F', 'aquifer': False, 'priority': 2},
        # Aquifer targets 5m+
        {'name': 'Saturated Sand',    'rho_min': 10,   'rho_max': 80,     'depth_min': 5,    'depth_max': None, 'color': '#4169E1', 'aquifer': True,  'priority': 3},
        {'name': 'Sand & Gravel',     'rho_min': 80,   'rho_max': 600,    'depth_min': 5,    'depth_max': None, 'color': '#1E90FF', 'aquifer': True,  'priority': 3},
        {'name': 'Gravel / Alluvium', 'rho_min': 600,  'rho_max': 1500,   'depth_min': 5,    'depth_max': None, 'color': '#00BFFF', 'aquifer': True,  'priority': 3},
        {'name': 'Sandstone',         'rho_min': 200,  'rho_max': 1000,   'depth_min': 8,    'depth_max': None, 'color': '#F4A460', 'aquifer': True,  'priority': 3},
        {'name': 'Limestone',         'rho_min': 500,  'rho_max': 5000,   'depth_min': 10,   'depth_max': None, 'color': '#B8860B', 'aquifer': True,  'priority': 3},
        {'name': 'Saline Water Zone', 'rho_min': 0.1,  'rho_max': 3,      'depth_min': None, 'depth_max': None, 'color': '#DC143C', 'aquifer': False, 'priority': 2},
        {'name': 'Hard Bedrock',      'rho_min': 2000, 'rho_max': 100000, 'depth_min': 10,   'depth_max': None, 'color': '#696969', 'aquifer': False, 'priority': 4},
    ]

    # ── BASEMENT COMPLEX CATALOG
    BASEMENT = [
        # Zone 0-6m: topsoil / laterite
        {'name': 'Lateritic Topsoil',  'rho_min': 100,  'rho_max': 600,    'depth_min': 0,    'depth_max': 6,    'color': '#CD5C5C', 'aquifer': False, 'priority': 1},
        {'name': 'Moist Topsoil',      'rho_min': 20,   'rho_max': 100,    'depth_min': 0,    'depth_max': 6,    'color': '#A0522D', 'aquifer': False, 'priority': 1},
        {'name': 'Humic/Clay Topsoil', 'rho_min': 5,    'rho_max': 20,     'depth_min': 0,    'depth_max': 6,    'color': '#6B3A2A', 'aquifer': False, 'priority': 1},
        # Regolith / weathered zone 3-20m
        {'name': 'Clay Regolith',      'rho_min': 1,    'rho_max': 30,     'depth_min': 3,    'depth_max': 20,   'color': '#708090', 'aquifer': False, 'priority': 2},
        {'name': 'Weathered Basement', 'rho_min': 30,   'rho_max': 250,    'depth_min': 4,    'depth_max': 40,   'color': '#CD853F', 'aquifer': True,  'priority': 3},
        {'name': 'Partly Weathered',   'rho_min': 250,  'rho_max': 800,    'depth_min': 8,    'depth_max': 50,   'color': '#DEB887', 'aquifer': True,  'priority': 3},
        # Fractured / fresh basement 15m+
        {'name': 'Fractured Basement', 'rho_min': 800,  'rho_max': 3000,   'depth_min': 15,   'depth_max': None, 'color': '#00CED1', 'aquifer': True,  'priority': 4},
        {'name': 'Fresh Basement',     'rho_min': 3000, 'rho_max': 100000, 'depth_min': 10,   'depth_max': None, 'color': '#2F4F4F', 'aquifer': False, 'priority': 4},
    ]

    # Forced topsoil fallback tables (used when depth < threshold)
    FORCED_TOPSOIL = {
        'sedimentary': [
            {'name': 'Dry Topsoil',   'rho_min': 100,  'rho_max': 1e9,  'color': '#8B4513'},
            {'name': 'Moist Topsoil', 'rho_min': 20,   'rho_max': 100,  'color': '#A0522D'},
            {'name': 'Humic Topsoil', 'rho_min': 0,    'rho_max': 20,   'color': '#6B3A2A'},
        ],
        'basement': [
            {'name': 'Lateritic Topsoil',  'rho_min': 100, 'rho_max': 1e9, 'color': '#CD5C5C'},
            {'name': 'Moist Topsoil',      'rho_min': 20,  'rho_max': 100, 'color': '#A0522D'},
            {'name': 'Humic/Clay Topsoil', 'rho_min': 0,   'rho_max': 20,  'color': '#6B3A2A'},
        ]
    }

    def classify_layer(self, rho: float, terrain: str, depth: float = 0) -> dict:
        """
        Classify a single layer using resistivity AND depth context.

        Priority rules:
          1. depth < TOPSOIL_DEPTH_THRESHOLD  => forced topsoil (no exceptions)
          2. depth >= threshold               => catalog filtered by depth_min/depth_max,
                                                 scored by rho fit + priority weight
          3. No depth-filtered match          => nearest-neighbour fallback
        """
        terrain = terrain.lower()
        catalog = self.SEDIMENTARY if terrain == 'sedimentary' else self.BASEMENT
        forced  = self.FORCED_TOPSOIL.get(terrain, self.FORCED_TOPSOIL['sedimentary'])

        # ── RULE 1: Shallow layer => always topsoil/overburden
        if depth < self.TOPSOIL_DEPTH_THRESHOLD:
            for ts in forced:
                if ts['rho_min'] <= rho < ts['rho_max']:
                    return {'name': ts['name'], 'color': ts['color'],
                            'is_aquifer': False, 'rho': rho, 'depth': depth,
                            'confidence': 'High (depth rule: 0-5m = overburden)'}
            # Fallback: pick closest forced topsoil by rho
            return {'name': forced[0]['name'], 'color': forced[0]['color'],
                    'is_aquifer': False, 'rho': rho, 'depth': depth,
                    'confidence': 'Medium (depth rule applied, rho outside normal topsoil range)'}

        # ── RULE 2: Depth-filtered catalog match
        valid = [
            e for e in catalog
            if (e['depth_min'] is None or depth >= e['depth_min'])
            and (e['depth_max'] is None or depth < e['depth_max'])
        ]

        best = None
        best_score = -1
        for entry in valid:
            if entry['rho_min'] <= rho <= entry['rho_max']:
                rng    = entry['rho_max'] - entry['rho_min'] + 1e-10
                centre = (entry['rho_min'] + entry['rho_max']) / 2
                score  = (1 - abs(rho - centre) / rng) * entry['priority']
                if score > best_score:
                    best_score = score
                    best = entry

        if best:
            conf = 'High' if best_score > 1.5 else 'Medium'
            return {'name': best['name'], 'color': best['color'],
                    'is_aquifer': best['aquifer'], 'rho': rho, 'depth': depth,
                    'confidence': conf}

        # ── RULE 3: Nearest-neighbour fallback
        fallback_list = valid if valid else catalog
        distances = [min(abs(rho - e['rho_min']), abs(rho - e['rho_max']))
                     for e in fallback_list]
        best = fallback_list[int(np.argmin(distances))]
        return {'name': best['name'], 'color': best['color'],
                'is_aquifer': best['aquifer'], 'rho': rho, 'depth': depth,
                'confidence': 'Low (nearest-neighbour fallback)'}

    def classify_all_layers(self, result: dict, terrain: str) -> list:
        """Classify all inverted layers with depth-informed rules."""
        layers = []
        rhos = result['resistivities']
        ths  = result['thicknesses']
        deps = result['depths']

        for i, rho in enumerate(rhos):
            depth_top = deps[i]
            thickness = ths[i] if i < len(ths) else None
            cls = self.classify_layer(rho, terrain, depth=depth_top)
            cls['layer_num']  = i + 1
            cls['thickness']  = thickness
            cls['depth_top']  = depth_top
            cls['depth_bot']  = (depth_top + thickness) if thickness else None
            layers.append(cls)
        return layers

    def print_layers(self, layers: list) -> None:
        print(f"\n{'='*80}")
        print("  GEOLOGICAL LAYER INTERPRETATION  (Depth + Resistivity Informed)")
        print(f"{'='*80}")
        print(f"  {'#':<3} {'Lithology':<22} {'ρ(Ω·m)':>9} {'Depth':>9} {'Thick':>8} {'Aquifer?':>9}  Confidence")
        print(f"{'─'*80}")
        for l in layers:
            h  = f"{l['thickness']:.1f}m" if l['thickness'] else '∞'
            d  = f"{l['depth_top']:.1f}m"
            aq = '✅ YES' if l['is_aquifer'] else 'No'
            print(f"  {l['layer_num']:<3} {l['name']:<22} {l['rho']:>9.1f} {d:>9} {h:>8} {aq:>9}  {l['confidence']}")
        print(f"{'='*80}")
