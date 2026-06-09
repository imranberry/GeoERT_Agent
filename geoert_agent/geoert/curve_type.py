"""Module 4 — CurveTypeClassifier
Identifies VES log-log curve type from shape analysis and
layer resistivity sequence. Covers A, Q, H, K and compound types.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

class CurveTypeClassifier:
    """
    Identifies VES log-log curve type from:
      (a) apparent resistivity field data — shape analysis
      (b) inverted layer resistivities    — sequence analysis (confirmation)

    3-layer types : A, Q, H, K
    4-layer types : HA, HK, KH, KQ, AA, QH, AK, QQ

    Reference: Orellana & Mooney (1966), Keller & Frischknecht (1966)
    """

    CURVE_INFO = {
        'A':  {'desc': 'Ascending',        'hydro': 'Resistivity increases with depth — compaction or lithification toward bedrock.',              'aquifer_likelihood': 'Low–Moderate', 'color': '#2196F3'},
        'Q':  {'desc': 'Descending',        'hydro': 'Resistivity decreases with depth — saline water or thick clay sequence.',                   'aquifer_likelihood': 'Low',          'color': '#F44336'},
        'H':  {'desc': 'Minimum (Bowl)',    'hydro': 'Conductive layer sandwiched between resistive layers — STRONG aquifer indicator.',          'aquifer_likelihood': 'HIGH',         'color': '#4CAF50'},
        'K':  {'desc': 'Maximum (Bell)',    'hydro': 'Resistive layer between conductive layers — possibly dry sand/gravel.',                     'aquifer_likelihood': 'Moderate',     'color': '#FF9800'},
        'HA': {'desc': 'H → Ascending',    'hydro': 'Aquifer layer overlying resistive basement — excellent borehole target.',                   'aquifer_likelihood': 'VERY HIGH',    'color': '#009688'},
        'HK': {'desc': 'H → K (4-layer)',  'hydro': 'Conductive middle layer with resistive below — weathered zone aquifer.',                    'aquifer_likelihood': 'HIGH',         'color': '#4CAF50'},
        'KH': {'desc': 'K → H (4-layer)',  'hydro': 'Resistive then conductive — fractured zone aquifer likely.',                                'aquifer_likelihood': 'HIGH',         'color': '#8BC34A'},
        'KQ': {'desc': 'K → Q (4-layer)',  'hydro': 'Resistive middle, deep conductive — saline water risk at depth.',                           'aquifer_likelihood': 'Moderate',     'color': '#FF5722'},
        'AA': {'desc': 'Double Ascending', 'hydro': 'Uniformly hardening sequence — deep basement, limited aquifer prospect.',                   'aquifer_likelihood': 'Low',          'color': '#9C27B0'},
        'QH': {'desc': 'Q → H (4-layer)',  'hydro': 'Clay overburden with conductive zone at depth — possible aquifer below clay.',              'aquifer_likelihood': 'Moderate',     'color': '#FF9800'},
        'AK': {'desc': 'A → K (4-layer)',  'hydro': 'Rising then peaked resistivity — dry resistive layer between conductors.',                  'aquifer_likelihood': 'Moderate',     'color': '#607D8B'},
        'QQ': {'desc': 'Double Descending','hydro': 'Deeply saline or clay-saturated — poor aquifer prospect throughout.',                       'aquifer_likelihood': 'Very Low',     'color': '#B71C1C'},
    }

    def classify_from_apparent(self, spacings: np.ndarray,
                                rho_a: np.ndarray) -> dict:
        """
        Detect curve type from the shape of the apparent resistivity log-log curve.
        Uses smoothed trend analysis to find minima, maxima, and overall slope.
        """
        log_rho = np.log10(np.clip(rho_a, 1e-3, None))
        log_s   = np.log10(np.clip(spacings, 1e-3, None))

        # Moving average smoothing (window=3) to reduce noise
        def smooth(arr, w=3):
            pad = w // 2
            padded = np.pad(arr, pad, mode='edge')
            return np.convolve(padded, np.ones(w)/w, mode='valid')[:len(arr)]

        sm = smooth(log_rho)

        # Detect local minima and maxima
        min_idx, max_idx = [], []
        for i in range(1, len(sm) - 1):
            if sm[i] < sm[i-1] and sm[i] < sm[i+1]:
                min_idx.append(i)
            if sm[i] > sm[i-1] and sm[i] > sm[i+1]:
                max_idx.append(i)

        has_min = len(min_idx) > 0
        has_max = len(max_idx) > 0

        # Overall trend (linear fit on log-log)
        overall_slope = float(np.polyfit(log_s, log_rho, 1)[0])

        curve_type = self._shape_to_type(has_min, has_max, min_idx, max_idx,
                                          overall_slope, sm)

        amplitude  = float(np.ptp(sm))  # peak-to-trough in log space
        confidence = 'High' if amplitude > 0.3 else 'Medium' if amplitude > 0.1 else 'Low'

        return {
            'curve_type':    curve_type,
            'has_minimum':   has_min,
            'has_maximum':   has_max,
            'min_idx':       min_idx,
            'max_idx':       max_idx,
            'overall_slope': overall_slope,
            'amplitude':     amplitude,
            'confidence':    confidence,
            'sm_rho':        sm,
            'info':          self.CURVE_INFO.get(curve_type, {}),
        }

    def _shape_to_type(self, has_min, has_max, min_idx, max_idx,
                        slope, sm) -> str:
        """Rule-based curve type from shape features."""
        n = len(sm)

        if has_min and has_max:
            first_min = min_idx[0]
            first_max = max_idx[0]
            return 'KH' if first_max < first_min else 'HK'

        if has_min:
            pos = min_idx[0]
            post = sm[pos:]
            if len(post) > 2:
                post_slope = float(np.polyfit(range(len(post)), post, 1)[0])
                return 'HA' if post_slope > 0.03 else 'H'
            return 'H'

        if has_max:
            pos = max_idx[0]
            post = sm[pos:]
            if len(post) > 2:
                post_slope = float(np.polyfit(range(len(post)), post, 1)[0])
                return 'KQ' if post_slope < -0.03 else 'K'
            return 'K'

        # Monotonic
        if slope > 0.05:
            d = np.diff(sm)
            return 'AA' if (np.mean(d[:n//2]) > 0 and
                            np.mean(d[n//2:]) > np.mean(d[:n//2])) else 'A'
        elif slope < -0.05:
            d = np.diff(sm)
            return 'QQ' if (np.mean(d[:n//2]) < 0 and
                            np.mean(d[n//2:]) < np.mean(d[:n//2])) else 'Q'
        return 'A'

    def classify_from_layers(self, resistivities: np.ndarray) -> dict:
        """
        Classify curve type from inverted layer resistivity sequence.
        More definitive than apparent curve shape — used as confirmation.
        """
        rho = list(resistivities)
        n   = len(rho)
        changes = tuple(
            'up' if rho[i+1] > rho[i] else 'down'
            for i in range(min(n-1, 3))
        )
        type_map = {
            ('up',):                  'A',
            ('down',):                'Q',
            ('down', 'up'):           'H',
            ('up', 'down'):           'K',
            ('down', 'up', 'up'):     'HA',
            ('down', 'up', 'down'):   'HK',
            ('up', 'down', 'up'):     'KH',
            ('up', 'down', 'down'):   'KQ',
            ('up', 'up', 'up'):       'AA',
            ('down', 'down', 'up'):   'QH',
            ('up', 'up', 'down'):     'AK',
            ('down', 'down', 'down'): 'QQ',
        }
        ct = type_map.get(changes, 'A')
        return {
            'curve_type':   ct,
            'rho_sequence': rho,
            'changes':      list(changes),
            'info':         self.CURVE_INFO.get(ct, {}),
        }

    def plot_curve_diagnosis(self, apparent: dict, layer: dict,
                              inv_result: dict,
                              site_name: str = '') -> 'plt.Figure':
        """Two-panel diagnostic: log-log curve annotated + layer bar chart."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        spacings = inv_result['spacings']
        rho_obs  = inv_result['rho_observed']
        rho_pred = inv_result['rho_predicted']
        ct       = apparent['curve_type']
        info     = self.CURVE_INFO.get(ct, {})
        box_col  = info.get('color', '#888888')

        # ── Left: annotated log-log curve
        ax1.loglog(spacings, rho_obs,  'o', color='#1E90FF',
                   markersize=7, label='Field Data', zorder=5)
        ax1.loglog(spacings, rho_pred, '-', color='#FF4500',
                   linewidth=2.5, label='Fitted Model', zorder=4)

        ax1.set_xlabel('Electrode Spacing AB/2 (m)', fontsize=11)
        ax1.set_ylabel('Apparent Resistivity ρₐ (Ω·m)', fontsize=11)
        ax1.set_title(
            f'VES Curve — Type {ct} ({info.get("desc","")})',
            fontsize=12, fontweight='bold'
        )
        ax1.legend(fontsize=10)

        # Type annotation box
        ax1.text(
            0.04, 0.96,
            f'Curve Type : {ct}\nAquifer Prob: {info.get("aquifer_likelihood","?")}\nDetection  : {apparent["confidence"]}',
            transform=ax1.transAxes, fontsize=9, fontweight='bold', va='top',
            bbox=dict(boxstyle='round,pad=0.45', facecolor=box_col, alpha=0.22, edgecolor=box_col)
        )

        # Annotate minimum (aquifer signal)
        if apparent['has_minimum']:
            mi = int(np.argmin(rho_obs))
            ax1.annotate(
                'ρ min\n(Aquifer signal?)',
                xy=(spacings[mi], rho_obs[mi]),
                xytext=(spacings[mi]*2.5, rho_obs[mi]*0.55),
                arrowprops=dict(arrowstyle='->', color='#4CAF50', lw=1.5),
                color='#4CAF50', fontsize=8, fontweight='bold'
            )
        # Annotate maximum
        if apparent['has_maximum']:
            mi = int(np.argmax(rho_obs))
            ax1.annotate(
                'ρ max\n(Resistive layer)',
                xy=(spacings[mi], rho_obs[mi]),
                xytext=(spacings[mi]*2.5, rho_obs[mi]*1.4),
                arrowprops=dict(arrowstyle='->', color='#F44336', lw=1.5),
                color='#F44336', fontsize=8, fontweight='bold'
            )

        # ── Right: layer resistivity bar chart with trend arrows
        rhos = inv_result['resistivities']
        lbls = [f'L{i+1}\n{r:.0f}Ω·m' for i, r in enumerate(rhos)]
        bar_colors = [
            '#4CAF50' if (i < len(rhos)-1 and rhos[i+1] < rhos[i]) else
            '#2196F3' if (i < len(rhos)-1 and rhos[i+1] > rhos[i]) else
            '#9E9E9E'
            for i in range(len(rhos))
        ]
        ax2.bar(lbls, rhos, color=bar_colors, edgecolor='black', linewidth=0.8)
        ax2.set_ylabel('Layer Resistivity (Ω·m)', fontsize=11)
        ax2.set_title(
            f'Inverted Layer Sequence → Type {layer["curve_type"]}\n'
            f'(Apparent: {ct}  |  Layer-confirmed: {layer["curve_type"]})',
            fontsize=11, fontweight='bold'
        )

        # Trend arrows between bars
        for i in range(len(rhos)-1):
            arrow = '↑' if rhos[i+1] > rhos[i] else '↓'
            col   = '#2196F3' if arrow == '↑' else '#4CAF50'
            ax2.text(i + 0.5, max(rhos[i], rhos[i+1]) * 1.04,
                     arrow, ha='center', fontsize=14, color=col, fontweight='bold')

        hydro = layer['info'].get('hydro', '')
        ax2.text(0.5, -0.18, hydro, transform=ax2.transAxes,
                 ha='center', fontsize=8.5, style='italic', color='#333333')

        if site_name:
            fig.suptitle(f'VES Curve Type Analysis — {site_name}',
                         fontsize=13, fontweight='bold', y=1.02)
        plt.tight_layout()
        return fig

    def print_report(self, apparent: dict, layer: dict) -> None:
        ct   = apparent['curve_type']
        info = self.CURVE_INFO.get(ct, {})
        lct  = layer['curve_type']
        agree = '✅ Agree' if ct == lct else f'⚠️  Mismatch (layer says {lct})'
        print(f"\n{'='*62}")
        print("  VES CURVE TYPE ANALYSIS")
        print(f"{'='*62}")
        print(f"  Apparent curve type   : {ct} — {info.get('desc','')}")
        print(f"  Layer-confirmed type  : {lct}       {agree}")
        print(f"  Has resistivity min   : {apparent['has_minimum']}")
        print(f"  Has resistivity max   : {apparent['has_maximum']}")
        print(f"  Overall trend (slope) : {apparent['overall_slope']:+.3f}  (+ ascending, - descending)")
        print(f"  Curve amplitude (log) : {apparent['amplitude']:.3f}")
        print(f"  Detection confidence  : {apparent['confidence']}")
        print(f"{'─'*62}")
        print(f"  Hydrogeological meaning:")
        print(f"    {info.get('hydro','Unknown')}")
        print(f"  Aquifer likelihood    : {info.get('aquifer_likelihood','?')}")
        print(f"  Layer ρ sequence      : {' → '.join(f'{r:.0f}' for r in layer['rho_sequence'])} Ω·m")
        print(f"{'='*62}")
