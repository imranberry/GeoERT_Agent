"""Module 3 — ERTCalculator
Computes apparent resistivity (rho_a) and geometric factor (K)
for Schlumberger, Wenner, and Dipole-Dipole arrays.
"""
import numpy as np
import pandas as pd

class ERTCalculator:
    """
    Computes apparent resistivity (rho_a) and geometric factor (K)
    for Schlumberger, Wenner, and Dipole-Dipole arrays.
    """

    ARRAY_TYPES = ['schlumberger', 'wenner', 'dipole_dipole']

    def compute(self, df: pd.DataFrame, array_type: str) -> pd.DataFrame:
        """
        Main entry point. Dispatches to the correct formula.
        Returns DataFrame with K and rho_a columns added.
        """
        array_type = array_type.lower().replace('-', '_').replace(' ', '_')
        if array_type not in self.ARRAY_TYPES:
            raise ValueError(f'Unknown array type: {array_type}. '
                             f'Choose from {self.ARRAY_TYPES}')

        df = df.copy()
        if array_type == 'schlumberger':
            return self._schlumberger(df)
        elif array_type == 'wenner':
            return self._wenner(df)
        elif array_type == 'dipole_dipole':
            return self._dipole_dipole(df)

    def _schlumberger(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Schlumberger array.
        Columns needed: AB_2 (AB/2), MN_2 (MN/2), Voltage_mV, Current_mA
        """
        AB2 = df['AB_2'].values
        MN2 = df['MN_2'].values
        dV  = df['Voltage_mV'].values / 1000  # convert mV → V
        I   = df['Current_mA'].values / 1000  # convert mA → A

        # Validate: AB/2 must be > MN/2
        if np.any(AB2 <= MN2):
            raise ValueError('AB/2 must be greater than MN/2 for all readings')

        K     = np.pi * ((AB2**2 - MN2**2) / (2 * MN2))
        rho_a = K * (np.abs(dV) / np.abs(I))

        df['K']       = K
        df['rho_a']   = rho_a
        df['spacing'] = AB2   # Use AB/2 as the depth proxy for plotting
        df['array']   = 'Schlumberger'
        return df

    def _wenner(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Wenner array.
        Columns needed: a_spacing, Voltage_mV, Current_mA
        """
        a   = df['a_spacing'].values
        dV  = df['Voltage_mV'].values / 1000
        I   = df['Current_mA'].values / 1000

        K     = 2 * np.pi * a
        rho_a = K * (np.abs(dV) / np.abs(I))

        df['K']       = K
        df['rho_a']   = rho_a
        df['spacing'] = a
        df['array']   = 'Wenner'
        return df

    def _dipole_dipole(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Dipole-Dipole array.
        Columns needed: a_spacing, n_factor, Voltage_mV, Current_mA
        """
        a   = df['a_spacing'].values
        n   = df['n_factor'].values
        dV  = df['Voltage_mV'].values / 1000
        I   = df['Current_mA'].values / 1000

        K     = np.pi * n * (n + 1) * (n + 2) * a
        rho_a = K * (np.abs(dV) / np.abs(I))

        df['K']       = K
        df['rho_a']   = rho_a
        df['spacing'] = a * n   # Pseudo-depth proxy
        df['array']   = 'Dipole-Dipole'
        return df

    def summary(self, df: pd.DataFrame) -> None:
        """Print a clean summary of computed resistivities."""
        print(f"\n{'='*55}")
        print(f"  ERT APPARENT RESISTIVITY — {df['array'].iloc[0]}")
        print(f"{'='*55}")
        print(f"  Readings   : {len(df)}")
        print(f"  ρₐ min     : {df['rho_a'].min():.2f} Ω·m")
        print(f"  ρₐ max     : {df['rho_a'].max():.2f} Ω·m")
        print(f"  ρₐ mean    : {df['rho_a'].mean():.2f} Ω·m")
        print(f"  K min/max  : {df['K'].min():.2f} / {df['K'].max():.2f}")
        print(f"{'='*55}")
        print(df[['spacing', 'K', 'rho_a']].round(3).to_string(index=False))
