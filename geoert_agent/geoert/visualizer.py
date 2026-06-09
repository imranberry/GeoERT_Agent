"""Module 9 — Visualizer
Generates all ERT interpretation plots:
  log-log curve, 2D layer model, Dar-Zarouk charts, 3D borehole, dashboard.
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.gridspec as gridspec
from typing import List, Dict

class Visualizer:
    """
    Generates all ERT interpretation plots.
    """

    def __init__(self, site_name: str = 'Study Area'):
        self.site_name = site_name

    # ────────────────────────────────────────────
    # 1. LOG-LOG PLOT
    # ────────────────────────────────────────────
    def plot_log_log(self, inv_result: Dict, array_type: str,
                      ax=None, save_path: str = None) -> plt.Figure:
        """Log-Log VES curve with fitted model."""
        standalone = ax is None
        if standalone:
            fig, ax = plt.subplots(figsize=(8, 6))
        else:
            fig = ax.get_figure()

        spacings = inv_result['spacings']
        rho_obs  = inv_result['rho_observed']
        rho_pred = inv_result['rho_predicted']

        ax.loglog(spacings, rho_obs, 'o', color='#1E90FF',
                  markersize=7, label='Field Data', zorder=5)
        ax.loglog(spacings, rho_pred, '-', color='#FF4500',
                  linewidth=2.5, label='Fitted Model', zorder=4)

        ax.set_xlabel('Electrode Spacing AB/2 (m)', fontsize=11)
        ax.set_ylabel('Apparent Resistivity ρₐ (Ω·m)', fontsize=11)
        ax.set_title(f'VES Log-Log Curve — {array_type} Array\n{self.site_name}',
                     fontsize=12, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, which='both', alpha=0.3)

        rms = inv_result['rms_error']
        ax.annotate(f'RMS = {rms:.4f}',
                    xy=(0.05, 0.05), xycoords='axes fraction',
                    fontsize=9, color='gray')

        if save_path and standalone:
            fig.savefig(save_path, bbox_inches='tight', dpi=150)
        return fig

    # ────────────────────────────────────────────
    # 2. 2D LAYER MODEL
    # ────────────────────────────────────────────
    def plot_layer_model(self, layers: List[Dict], aquifer_result: Dict,
                          ax=None, save_path: str = None) -> plt.Figure:
        """2D borehole-style layer model."""
        standalone = ax is None
        if standalone:
            fig, ax = plt.subplots(figsize=(5, 10))
        else:
            fig = ax.get_figure()

        ax.set_xlim(0, 1)
        max_depth = sum(l['thickness'] for l in layers if l['thickness']) + 5
        ax.set_ylim(-max_depth, 2)

        primary_aq = (aquifer_result['primary_aquifer']['layer_num']
                      if aquifer_result['aquifer_found'] else -1)

        y_cursor = 0
        for layer in layers:
            h = layer['thickness'] if layer['thickness'] else 10
            color = layer['color']
            y_top = -y_cursor
            y_bot = -(y_cursor + h)

            rect = mpatches.FancyBboxPatch(
                (0.05, y_bot), 0.9, h,
                boxstyle='square,pad=0',
                facecolor=color, edgecolor='black',
                linewidth=0.8, alpha=0.9
            )
            ax.add_patch(rect)

            # Label
            label_text = f"{layer['name']}\n{layer['rho']:.0f} Ω·m | {h:.1f}m"
            if layer['layer_num'] == primary_aq:
                label_text = f"💧 AQUIFER\n{layer['name']}\n{layer['rho']:.0f} Ω·m | {h:.1f}m"
                rect.set_linewidth(2.5)
                rect.set_edgecolor('#FFD700')

            mid_y = y_bot + h / 2
            ax.text(0.5, mid_y, label_text,
                    ha='center', va='center', fontsize=7.5,
                    color='white', fontweight='bold',
                    multialignment='center')

            # Depth marker
            ax.text(-0.02, y_top, f'{y_cursor:.0f}m',
                    ha='right', va='top', fontsize=7.5, color='black')

            y_cursor += h
            if not layer['thickness']:  # half-space hatching
                ax.fill_between([0.05, 0.95], [y_bot - 3, y_bot - 3],
                                [y_bot, y_bot], color=color,
                                hatch='///', alpha=0.5)

        ax.set_title(f'Layer Model\n{self.site_name}',
                     fontsize=11, fontweight='bold')
        ax.set_xticks([])
        ax.set_ylabel('Depth (m)', fontsize=10)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(
            lambda x, _: f'{-x:.0f}'
        ))

        if save_path and standalone:
            fig.savefig(save_path, bbox_inches='tight', dpi=150)
        return fig

    # ────────────────────────────────────────────
    # 3. DAR-ZAROUK BAR CHART
    # ────────────────────────────────────────────
    def plot_dar_zarouk(self, dz_result: Dict,
                         ax=None, save_path: str = None) -> plt.Figure:
        """Dar-Zarouk T and S bar chart."""
        standalone = ax is None
        if standalone:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
        else:
            fig = ax.get_figure()
            ax1 = ax
            ax2 = ax

        lp     = dz_result['layer_params']
        labels = [f"L{p['layer_num']}\n{p['lithology'][:10]}" for p in lp]
        T_vals = [p['T'] for p in lp]
        S_vals = [p['S'] for p in lp]
        colors = ['#1E90FF' if p['is_aquifer'] else
                  '#FF6347' if p['is_overburden'] else
                  '#808080' for p in lp]

        if standalone:
            # Transverse Resistance
            bars = ax1.bar(labels, T_vals, color=colors, edgecolor='black',
                           linewidth=0.8)
            ax1.set_title('Transverse Resistance T (Ω·m²)',
                          fontweight='bold')
            ax1.set_ylabel('T (Ω·m²)')
            for bar, val in zip(bars, T_vals):
                ax1.text(bar.get_x() + bar.get_width()/2,
                         bar.get_height() * 1.02,
                         f'{val:.0f}', ha='center', va='bottom', fontsize=8)

            # Longitudinal Conductance
            bars2 = ax2.bar(labels, S_vals, color=colors, edgecolor='black',
                            linewidth=0.8)
            ax2.set_title('Longitudinal Conductance S (Siemens)',
                          fontweight='bold')
            ax2.set_ylabel('S (Siemens)')
            for bar, val in zip(bars2, S_vals):
                ax2.text(bar.get_x() + bar.get_width()/2,
                         bar.get_height() * 1.02,
                         f'{val:.4f}', ha='center', va='bottom', fontsize=8)

            legend_patches = [
                mpatches.Patch(color='#1E90FF', label='Aquifer'),
                mpatches.Patch(color='#FF6347', label='Overburden'),
                mpatches.Patch(color='#808080', label='Substrate'),
            ]
            fig.legend(handles=legend_patches, loc='upper right',
                       fontsize=9, framealpha=0.8)

            v = dz_result['vulnerability']
            fig.suptitle(
                f'Dar-Zarouk Parameters — {self.site_name}\n'
                f'{v["icon"]} Vulnerability: {v["label"]}  '
                f'(ΣS_overburden = {dz_result["overburden_S"]:.4f} S)',
                fontsize=12, fontweight='bold'
            )
            plt.tight_layout()

        if save_path and standalone:
            fig.savefig(save_path, bbox_inches='tight', dpi=150)
        return fig

    # ────────────────────────────────────────────
    # 4. 3D BOREHOLE
    # ────────────────────────────────────────────
    def plot_3d_borehole(self, layers: List[Dict],
                          aquifer_result: Dict,
                          save_path: str = None) -> plt.Figure:
        """Pseudo-3D cylindrical borehole plot."""
        from mpl_toolkits.mplot3d import Axes3D
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        fig = plt.figure(figsize=(8, 10))
        ax  = fig.add_subplot(111, projection='3d')

        primary_aq = (aquifer_result['primary_aquifer']['layer_num']
                      if aquifer_result['aquifer_found'] else -1)

        theta = np.linspace(0, 2 * np.pi, 30)
        r = 0.4   # Borehole radius

        z_cursor = 0
        for layer in layers:
            h     = layer['thickness'] if layer['thickness'] else 8
            color = layer['color']
            z_top = -z_cursor
            z_bot = -(z_cursor + h)

            # Cylinder side surface
            x_cyl = r * np.cos(theta)
            y_cyl = r * np.sin(theta)

            for i in range(len(theta) - 1):
                verts = [
                    [(x_cyl[i], y_cyl[i], z_top),
                     (x_cyl[i+1], y_cyl[i+1], z_top),
                     (x_cyl[i+1], y_cyl[i+1], z_bot),
                     (x_cyl[i], y_cyl[i], z_bot)]
                ]
                poly = Poly3DCollection(verts, alpha=0.85)
                poly.set_facecolor(color)
                poly.set_edgecolor('black')
                poly.set_linewidth(0.2)
                ax.add_collection3d(poly)

            # Top cap
            x_cap = np.append(r * np.cos(theta), 0)
            y_cap = np.append(r * np.sin(theta), 0)
            z_cap = np.full_like(x_cap, z_top)
            ax.plot_trisurf(x_cap, y_cap, z_cap, color=color,
                            alpha=0.9, linewidth=0)

            # Label
            lbl = layer['name']
            if layer['layer_num'] == primary_aq:
                lbl = f'💧 {lbl}'
            ax.text(r + 0.1, 0, (z_top + z_bot) / 2,
                    f'{lbl}\n{layer["rho"]:.0f}Ω·m',
                    fontsize=6.5, va='center', color='black')

            z_cursor += h

        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Depth (m)')
        ax.set_title(f'3D Borehole Model\n{self.site_name}',
                     fontsize=12, fontweight='bold')

        # Clean depth tick labels
        z_ticks = ax.get_zticks()
        ax.set_zticklabels([f'{-t:.0f}' for t in z_ticks])
        ax.view_init(elev=20, azim=-60)

        plt.tight_layout()
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=150)
        return fig

    # ────────────────────────────────────────────
    # 5. COMBINED DASHBOARD
    # ────────────────────────────────────────────
    def plot_dashboard(self, inv_result: Dict, layers: List[Dict],
                        aquifer_result: Dict, dz_result: Dict,
                        array_type: str,
                        save_path: str = 'geoert_dashboard.png') -> plt.Figure:
        """Combined 4-panel interpretation dashboard."""
        fig = plt.figure(figsize=(18, 14))
        gs  = gridspec.GridSpec(2, 3, figure=fig,
                                hspace=0.38, wspace=0.35)

        # ── Panel 1: Log-Log
        ax1 = fig.add_subplot(gs[0, 0:2])
        self.plot_log_log(inv_result, array_type, ax=ax1)

        # ── Panel 2: Layer model
        ax2 = fig.add_subplot(gs[0:2, 2])
        self.plot_layer_model(layers, aquifer_result, ax=ax2)

        # ── Panel 3: T bar chart
        ax3 = fig.add_subplot(gs[1, 0])
        lp     = dz_result['layer_params']
        labels = [f"L{p['layer_num']}" for p in lp]
        T_vals = [p['T'] for p in lp]
        colors = ['#1E90FF' if p['is_aquifer'] else
                  '#FF6347' if p['is_overburden'] else
                  '#808080' for p in lp]
        ax3.bar(labels, T_vals, color=colors, edgecolor='black', linewidth=0.7)
        ax3.set_title('Transverse Resistance T (Ω·m²)', fontweight='bold', fontsize=10)
        ax3.set_ylabel('T (Ω·m²)')

        # ── Panel 4: S bar chart
        ax4 = fig.add_subplot(gs[1, 1])
        S_vals = [p['S'] for p in lp]
        ax4.bar(labels, S_vals, color=colors, edgecolor='black', linewidth=0.7)
        ax4.set_title('Longitudinal Conductance S (Siemens)', fontweight='bold', fontsize=10)
        ax4.set_ylabel('S (Siemens)')

        # ── Main title
        v = dz_result['vulnerability']
        aq = aquifer_result
        aq_text = (
            f"Aquifer: {aq['primary_aquifer']['lithology']} @ "
            f"{aq['primary_aquifer']['depth_top']:.1f}–"
            f"{aq['primary_aquifer']['depth_bottom']:.1f}m | "
            f"Yield: {aq['primary_aquifer']['yield_label']}"
            if aq['aquifer_found'] else 'No aquifer detected'
        )

        fig.suptitle(
            f'GeoERT Interpretation Dashboard — {self.site_name}\n'
            f'{aq_text}  |  '
            f'{v["icon"]} Contamination Vulnerability: {v["label"]}',
            fontsize=13, fontweight='bold', y=1.01
        )

        legend_patches = [
            mpatches.Patch(color='#1E90FF', label='Aquifer Layer'),
            mpatches.Patch(color='#FF6347', label='Overburden'),
            mpatches.Patch(color='#808080', label='Substrate/Bedrock'),
        ]
        fig.legend(handles=legend_patches, loc='lower center',
                   ncol=3, fontsize=9, framealpha=0.85,
                   bbox_to_anchor=(0.5, -0.02))

        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=150)
            print(f'  ✅ Dashboard saved to: {save_path}')
        return fig
