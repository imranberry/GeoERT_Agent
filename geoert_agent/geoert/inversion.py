"""Module 5 — Inversion1D
1D VES inversion using L-BFGS-B optimiser with Occam regularisation.
Recovers layer resistivities and thicknesses from apparent resistivity curve.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict

class Inversion1D:
    """
    1D VES inversion using iterative forward modelling.
    Recovers layer resistivities and thicknesses from apparent resistivity curve.

    Based on: Koefoed (1979) Geosounding Principles
    """

    def __init__(self, n_layers: int = 4):
        self.n_layers = n_layers
        self.fitted_resistivities = None
        self.fitted_thicknesses = None
        self.rms_error = None
        self.history = []

    def _forward(self, spacings, resistivities, thicknesses):
        """
        Forward model: compute theoretical apparent resistivity
        using the recursive T-matrix method.
        """
        depths = np.cumsum(thicknesses)
        rho_a = []

        for s in spacings:
            # Simplified layer weighting kernel
            # Proper implementation uses Hankel transform filter coefficients
            rho = self._kernel(s, resistivities, depths)
            rho_a.append(rho)

        return np.array(rho_a)

    def _kernel(self, s, rho_list, depths):
        """
        Approximate apparent resistivity kernel.
        Uses depth-weighted harmonic/arithmetic blend.
        """
        # Effective depth of investigation ≈ s/2 to s (Schlumberger)
        depth_inv = s * 0.6
        n = len(rho_list)
        boundaries = [0] + list(depths)

        # Find layers within depth of investigation
        weights = []
        for i in range(n):
            top = boundaries[i]
            bot = boundaries[i + 1] if i < len(depths) else depth_inv * 3
            overlap = max(0, min(bot, depth_inv) - top)
            weights.append(overlap)

        total = sum(weights)
        if total == 0:
            return rho_list[-1]

        # Geometric mean weighted by thickness
        log_rho = sum(w * np.log(r) for w, r in zip(weights, rho_list)) / total
        return np.exp(log_rho)

    def _objective(self, params, spacings, rho_obs):
        """RMS misfit between observed and modelled apparent resistivity."""
        n = self.n_layers
        log_rho = params[:n]
        log_h   = params[n:]

        resistivities = np.exp(log_rho)
        thicknesses   = np.exp(log_h)

        rho_calc = self._forward(spacings, resistivities, thicknesses)

        # Log-space RMS (better for orders-of-magnitude data)
        rms = np.sqrt(np.mean((np.log(rho_calc) - np.log(rho_obs))**2))

        # Smoothness regularization (Occam)
        smooth = 0.01 * np.sum(np.diff(log_rho)**2)

        self.history.append(rms)
        return rms + smooth

    def invert(self, df: pd.DataFrame, terrain: str = 'sedimentary',
               max_iter: int = 500) -> Dict:
        """
        Main inversion routine.

        Args:
            df: DataFrame with 'spacing' and 'rho_a' columns (from ERTCalculator)
            terrain: 'sedimentary' or 'basement'
            max_iter: maximum optimizer iterations

        Returns:
            dict with resistivities, thicknesses, depths, rms_error
        """
        spacings = df['spacing'].values
        rho_obs  = df['rho_a'].values
        n = self.n_layers

        # ── Starting model (log-space)
        rho_min, rho_max = rho_obs.min(), rho_obs.max()
        rho0 = np.logspace(np.log10(rho_min), np.log10(rho_max), n)
        h0   = np.full(n - 1, spacings.max() / (2 * (n - 1)))

        # Terrain-informed starting guess
        if terrain == 'sedimentary':
            rho0 = np.array([100, 20, 300, 2000])[:n]
            h0   = np.array([3, 8, 12])[:n-1]
        else:
            rho0 = np.array([80, 50, 600, 7000])[:n]
            h0   = np.array([4, 10, 8])[:n-1]

        x0 = np.concatenate([np.log(rho0), np.log(h0)])

        # ── Bounds (log-space)
        rho_bounds = [(np.log(1), np.log(50000))] * n
        h_bounds   = [(np.log(0.5), np.log(100))] * (n - 1)
        bounds = rho_bounds + h_bounds

        # ── Optimization
        self.history = []
        result = minimize(
            self._objective,
            x0,
            args=(spacings, rho_obs),
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': max_iter, 'ftol': 1e-9}
        )

        # ── Extract solution
        log_rho = result.x[:n]
        log_h   = result.x[n:]

        self.fitted_resistivities = np.exp(log_rho)
        self.fitted_thicknesses   = np.exp(log_h)
        self.rms_error = result.fun

        depths = np.cumsum(self.fitted_thicknesses)
        depths = np.concatenate([[0], depths])

        # ── Predicted curve
        rho_predicted = self._forward(
            spacings,
            self.fitted_resistivities,
            self.fitted_thicknesses
        )

        return {
            'resistivities': self.fitted_resistivities,
            'thicknesses':   self.fitted_thicknesses,
            'depths':        depths,
            'rms_error':     self.rms_error,
            'rho_predicted': rho_predicted,
            'spacings':      spacings,
            'rho_observed':  rho_obs,
            'converged':     result.success,
            'n_iter':        len(self.history)
        }

    def print_model(self, result: Dict) -> None:
        """Pretty-print the inverted layer model."""
        print(f"\n{'='*55}")
        print("  INVERTED LAYER MODEL")
        print(f"{'='*55}")
        print(f"  RMS Error  : {result['rms_error']:.4f} (log-space)")
        print(f"  Converged  : {result['converged']}")
        print(f"  Iterations : {result['n_iter']}")
        print(f"{'─'*55}")
        print(f"  {'Layer':<8} {'Resistivity':>14} {'Thickness':>12} {'Depth Top':>12}")
        print(f"{'─'*55}")

        rhos = result['resistivities']
        ths  = result['thicknesses']
        deps = result['depths']

        for i, rho in enumerate(rhos):
            h    = f"{ths[i]:.1f} m" if i < len(ths) else "∞ (half-space)"
            dtop = f"{deps[i]:.1f} m"
            print(f"  {i+1:<8} {rho:>12.1f} Ω·m  {h:>10}   {dtop:>10}")
        print(f"{'='*55}")
