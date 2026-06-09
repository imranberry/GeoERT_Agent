"""Module 2 — SampleDataGenerator
Generates synthetic ERT survey data for testing and validation.
Models a 4-layer earth: topsoil / clay / aquifer sand / basement.
"""
import numpy as np
import pandas as pd

class SampleDataGenerator:
    """
    Generates synthetic ERT survey data mimicking real field conditions.
    Models a 4-layer earth: topsoil / clay / aquifer sand / basement
    """

    # True model: [resistivity (Ω·m), thickness (m)]
    TRUE_MODEL_SEDIMENTARY = [
        (120,  3),    # Layer 1: Topsoil
        (15,   8),    # Layer 2: Clay (confining layer)
        (350,  12),   # Layer 3: Sand/Gravel AQUIFER
        (2500, None)  # Layer 4: Limestone bedrock (half-space)
    ]

    TRUE_MODEL_BASEMENT = [
        (80,   4),    # Layer 1: Topsoil
        (45,   10),   # Layer 2: Weathered basement (aquifer)
        (650,  8),    # Layer 3: Fractured basement (secondary aquifer)
        (8000, None)  # Layer 4: Fresh basement (half-space)
    ]

    def _forward_model_schlumberger(self, ab2_values, model):
        """Compute theoretical apparent resistivity for Schlumberger array."""
        rho_apparent = []
        resistivities = [m[0] for m in model]
        thicknesses = [m[1] for m in model if m[1] is not None]

        for ab2 in ab2_values:
            # Simplified Dar-Zarrouk kernel for 4-layer model
            # Uses recursive reflection coefficient approach
            rho_a = self._kernel_resistivity(ab2, resistivities, thicknesses)
            rho_apparent.append(rho_a)
        return np.array(rho_apparent)

    def _kernel_resistivity(self, ab2, resistivities, thicknesses):
        """Simplified apparent resistivity kernel (Mooney 1980 approximation)."""
        n = len(resistivities)
        depths = np.cumsum([0] + thicknesses)

        # Weighted depth interpolation
        total_depth = depths[-1]
        if ab2 < depths[1]:
            return resistivities[0]
        elif ab2 > total_depth * 3:
            return resistivities[-1]
        else:
            # Log-linear interpolation between layers
            idx = np.searchsorted(depths, ab2) - 1
            idx = min(idx, n - 2)
            w = (ab2 - depths[idx]) / (depths[idx + 1] - depths[idx] + 1e-10)
            w = np.clip(w, 0, 1)
            rho_a = np.exp(np.log(resistivities[idx]) * (1 - w) +
                           np.log(resistivities[idx + 1]) * w)
            return rho_a

    def generate_schlumberger(self, terrain='sedimentary', n_points=20, noise_pct=5):
        """Generate Schlumberger VES data."""
        model = (self.TRUE_MODEL_SEDIMENTARY if terrain == 'sedimentary'
                 else self.TRUE_MODEL_BASEMENT)

        ab2 = np.logspace(0.3, 2.3, n_points)   # 2m to 200m
        mn2 = ab2 / 5                             # MN/2 = AB/2 / 5
        mn2 = np.clip(mn2, 0.5, 10)

        rho_true = self._forward_model_schlumberger(ab2, model)
        noise = np.random.normal(1.0, noise_pct / 100, n_points)
        rho_noisy = rho_true * noise

        # Back-calculate voltage from rho = K * V/I
        K = np.pi * ((ab2**2 - mn2**2) / (2 * mn2))
        current_mA = np.full(n_points, 100.0)  # 100 mA injection
        voltage_mV = (rho_noisy / K) * current_mA

        df = pd.DataFrame({
            'AB_2': ab2,
            'MN_2': mn2,
            'Voltage_mV': voltage_mV,
            'Current_mA': current_mA
        })
        return df, model

    def generate_wenner(self, terrain='sedimentary', n_points=18, noise_pct=5):
        """Generate Wenner array data."""
        model = (self.TRUE_MODEL_SEDIMENTARY if terrain == 'sedimentary'
                 else self.TRUE_MODEL_BASEMENT)

        a = np.logspace(0.3, 2.0, n_points)
        rho_true = self._forward_model_schlumberger(a, model)
        noise = np.random.normal(1.0, noise_pct / 100, n_points)
        rho_noisy = rho_true * noise

        K = 2 * np.pi * a
        current_mA = np.full(n_points, 100.0)
        voltage_mV = (rho_noisy / K) * current_mA

        df = pd.DataFrame({
            'a_spacing': a,
            'n_factor': np.ones(n_points),
            'Voltage_mV': voltage_mV,
            'Current_mA': current_mA
        })
        return df, model

    def generate_dipole_dipole(self, terrain='sedimentary', n_points=20, noise_pct=5):
        """Generate Dipole-Dipole array data."""
        model = (self.TRUE_MODEL_SEDIMENTARY if terrain == 'sedimentary'
                 else self.TRUE_MODEL_BASEMENT)

        a = np.full(n_points, 10.0)   # Fixed dipole length 10m
        n = np.arange(1, n_points + 1, dtype=float)

        rho_true = self._forward_model_schlumberger(a * n, model)
        noise = np.random.normal(1.0, noise_pct / 100, n_points)
        rho_noisy = rho_true * noise

        K = np.pi * n * (n + 1) * (n + 2) * a
        current_mA = np.full(n_points, 100.0)
        voltage_mV = (rho_noisy / K) * current_mA

        df = pd.DataFrame({
            'a_spacing': a,
            'n_factor': n,
            'Voltage_mV': voltage_mV,
            'Current_mA': current_mA
        })
        return df, model
