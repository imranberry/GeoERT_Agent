"""
tests/test_all_modules.py
=========================
Unit tests for every GeoERT module.
Run with: pytest tests/ -v
"""

import pytest
import numpy as np
import pandas as pd
import sys
import os

# Make sure the package is importable from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from geoert.sample_data import SampleDataGenerator
from geoert.ert_calculator import ERTCalculator
from geoert.curve_type import CurveTypeClassifier
from geoert.inversion import Inversion1D
from geoert.terrain_classifier import TerrainClassifier
from geoert.aquifer_detector import AquiferDetector
from geoert.dar_zarouk import DarZarouk


# ─────────────────────────────────────────────────────────────
# Fixtures (shared test data)
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def schlum_df():
    """Synthetic Schlumberger data — sedimentary terrain."""
    np.random.seed(42)
    gen = SampleDataGenerator()
    df, _ = gen.generate_schlumberger(terrain="sedimentary", noise_pct=2)
    return df

@pytest.fixture(scope="module")
def ert_result(schlum_df):
    """Computed apparent resistivity from Schlumberger data."""
    calc = ERTCalculator()
    return calc.compute(schlum_df, "schlumberger")

@pytest.fixture(scope="module")
def inv_result(ert_result):
    """Inverted layer model."""
    inv = Inversion1D(n_layers=4)
    return inv.invert(ert_result, terrain="sedimentary", max_iter=200)

@pytest.fixture(scope="module")
def layers(inv_result):
    """Classified geological layers."""
    tc = TerrainClassifier()
    return tc.classify_all_layers(inv_result, terrain="sedimentary")

@pytest.fixture(scope="module")
def aquifer_result(layers):
    """Aquifer detection result."""
    det = AquiferDetector()
    return det.detect(layers, terrain="sedimentary")

@pytest.fixture(scope="module")
def dz_result(layers, aquifer_result):
    """Dar-Zarouk parameters."""
    dz = DarZarouk()
    return dz.compute(layers, aquifer_result)


# ─────────────────────────────────────────────────────────────
# Module 2: SampleDataGenerator
# ─────────────────────────────────────────────────────────────

class TestSampleDataGenerator:

    def test_schlumberger_shape(self, schlum_df):
        assert isinstance(schlum_df, pd.DataFrame)
        assert len(schlum_df) == 20
        assert set(["AB_2", "MN_2", "Voltage_mV", "Current_mA"]).issubset(schlum_df.columns)

    def test_schlumberger_ab_greater_than_mn(self, schlum_df):
        assert (schlum_df["AB_2"] > schlum_df["MN_2"]).all()

    def test_wenner_generates(self):
        np.random.seed(0)
        gen = SampleDataGenerator()
        df, _ = gen.generate_wenner(terrain="sedimentary")
        assert len(df) == 18
        assert "a_spacing" in df.columns

    def test_dipole_dipole_generates(self):
        np.random.seed(0)
        gen = SampleDataGenerator()
        df, _ = gen.generate_dipole_dipole(terrain="basement")
        assert len(df) == 20
        assert "n_factor" in df.columns

    def test_noise_adds_variability(self):
        gen = SampleDataGenerator()
        np.random.seed(1)
        df1, _ = gen.generate_schlumberger(noise_pct=0)
        np.random.seed(1)
        df2, _ = gen.generate_schlumberger(noise_pct=10)
        # With noise, voltages should differ
        assert not df1["Voltage_mV"].equals(df2["Voltage_mV"])


# ─────────────────────────────────────────────────────────────
# Module 3: ERTCalculator
# ─────────────────────────────────────────────────────────────

class TestERTCalculator:

    def test_schlumberger_adds_columns(self, ert_result):
        assert "K" in ert_result.columns
        assert "rho_a" in ert_result.columns
        assert "spacing" in ert_result.columns
        assert "array" in ert_result.columns

    def test_resistivities_positive(self, ert_result):
        assert (ert_result["rho_a"] > 0).all()

    def test_geometric_factors_positive(self, ert_result):
        assert (ert_result["K"] > 0).all()

    def test_array_label(self, ert_result):
        assert ert_result["array"].iloc[0] == "Schlumberger"

    def test_invalid_array_raises(self, schlum_df):
        calc = ERTCalculator()
        with pytest.raises(ValueError):
            calc.compute(schlum_df, "invalid_array")

    def test_wenner_formula(self):
        """K_wenner = 2πa — verify a single reading."""
        calc = ERTCalculator()
        df = pd.DataFrame({
            "a_spacing":   [10.0],
            "n_factor":    [1.0],
            "Voltage_mV":  [100.0],
            "Current_mA":  [100.0],
        })
        result = calc.compute(df, "wenner")
        expected_K = 2 * np.pi * 10.0
        assert abs(result["K"].iloc[0] - expected_K) < 1e-6

    def test_dipole_dipole_formula(self):
        """K_dd = π·n(n+1)(n+2)·a"""
        calc = ERTCalculator()
        a, n = 10.0, 2.0
        df = pd.DataFrame({
            "a_spacing": [a], "n_factor": [n],
            "Voltage_mV": [50.0], "Current_mA": [100.0],
        })
        result = calc.compute(df, "dipole_dipole")
        expected_K = np.pi * n * (n + 1) * (n + 2) * a
        assert abs(result["K"].iloc[0] - expected_K) < 1e-6

    def test_normalisation_variants(self, schlum_df):
        """'Schlumberger', 'SCHLUMBERGER', 'schlumberger' all work."""
        calc = ERTCalculator()
        for variant in ["Schlumberger", "SCHLUMBERGER", "schlumberger"]:
            result = calc.compute(schlum_df, variant)
            assert "rho_a" in result.columns


# ─────────────────────────────────────────────────────────────
# Module 4: CurveTypeClassifier
# ─────────────────────────────────────────────────────────────

class TestCurveTypeClassifier:

    def test_h_type_from_layers(self):
        ctc = CurveTypeClassifier()
        result = ctc.classify_from_layers([150, 10, 500, 2000])
        assert result["curve_type"] == "H"

    def test_k_type_from_layers(self):
        ctc = CurveTypeClassifier()
        result = ctc.classify_from_layers([100, 800, 50, 3000])
        assert result["curve_type"] == "K"

    def test_a_type_from_layers(self):
        ctc = CurveTypeClassifier()
        result = ctc.classify_from_layers([50, 150, 400, 1500])
        assert result["curve_type"] in ("A", "AA")

    def test_q_type_from_layers(self):
        ctc = CurveTypeClassifier()
        result = ctc.classify_from_layers([300, 100, 30, 5])
        assert result["curve_type"] in ("Q", "QQ")

    def test_ha_type_from_layers(self):
        ctc = CurveTypeClassifier()
        result = ctc.classify_from_layers([200, 15, 400, 2000])
        assert result["curve_type"] == "HA"

    def test_classify_from_apparent(self, ert_result):
        ctc = CurveTypeClassifier()
        result = ctc.classify_from_apparent(
            ert_result["spacing"].values,
            ert_result["rho_a"].values
        )
        assert "curve_type" in result
        assert result["curve_type"] in ctc.CURVE_INFO

    def test_result_has_hydro_info(self):
        ctc = CurveTypeClassifier()
        result = ctc.classify_from_layers([150, 10, 500, 2000])
        assert "info" in result
        assert "hydro" in result["info"]
        assert "aquifer_likelihood" in result["info"]


# ─────────────────────────────────────────────────────────────
# Module 5: Inversion1D
# ─────────────────────────────────────────────────────────────

class TestInversion1D:

    def test_result_keys(self, inv_result):
        required = ["resistivities", "thicknesses", "depths",
                    "rms_error", "rho_predicted", "spacings",
                    "rho_observed", "converged", "n_iter"]
        for k in required:
            assert k in inv_result, f"Missing key: {k}"

    def test_correct_number_of_layers(self, inv_result):
        assert len(inv_result["resistivities"]) == 4
        assert len(inv_result["thicknesses"]) == 3  # n-1 thicknesses

    def test_resistivities_positive(self, inv_result):
        assert all(r > 0 for r in inv_result["resistivities"])

    def test_thicknesses_positive(self, inv_result):
        assert all(h > 0 for h in inv_result["thicknesses"])

    def test_depths_non_decreasing(self, inv_result):
        depths = inv_result["depths"]
        assert all(depths[i] <= depths[i+1] for i in range(len(depths)-1))

    def test_rms_reasonable(self, inv_result):
        # RMS error should be small (good fit) for synthetic data
        assert inv_result["rms_error"] < 1.0

    def test_predicted_length_matches_observed(self, inv_result):
        assert len(inv_result["rho_predicted"]) == len(inv_result["rho_observed"])

    def test_basement_terrain_runs(self):
        np.random.seed(99)
        gen = SampleDataGenerator()
        df, _ = gen.generate_wenner(terrain="basement")
        calc = ERTCalculator()
        ert = calc.compute(df, "wenner")
        inv = Inversion1D(n_layers=4)
        result = inv.invert(ert, terrain="basement", max_iter=100)
        assert len(result["resistivities"]) == 4


# ─────────────────────────────────────────────────────────────
# Module 6: TerrainClassifier
# ─────────────────────────────────────────────────────────────

class TestTerrainClassifier:

    def test_shallow_layer_is_topsoil(self):
        tc = TerrainClassifier()
        # 2500 Ω·m at 1m depth should NOT be classified as Hard Bedrock
        result = tc.classify_layer(2500, "sedimentary", depth=1.0)
        assert result["is_aquifer"] is False
        assert "Topsoil" in result["name"] or "topsoil" in result["name"].lower()

    def test_deep_high_rho_can_be_bedrock(self):
        tc = TerrainClassifier()
        result = tc.classify_layer(5000, "sedimentary", depth=25.0)
        assert "Bedrock" in result["name"] or "Basement" in result["name"]

    def test_aquifer_only_below_5m(self):
        tc = TerrainClassifier()
        shallow = tc.classify_layer(300, "sedimentary", depth=2.0)
        deep    = tc.classify_layer(300, "sedimentary", depth=12.0)
        assert shallow["is_aquifer"] is False
        assert deep["is_aquifer"] is True

    def test_basement_terrain_catalog(self):
        tc = TerrainClassifier()
        result = tc.classify_layer(150, "basement", depth=20.0)
        assert result["is_aquifer"] is True  # Weathered Basement

    def test_all_layers_have_required_keys(self, layers):
        required = ["name", "color", "is_aquifer", "rho", "depth",
                    "layer_num", "thickness", "depth_top", "depth_bot"]
        for layer in layers:
            for k in required:
                assert k in layer, f"Layer missing key: {k}"

    def test_layer_numbers_sequential(self, layers):
        nums = [l["layer_num"] for l in layers]
        assert nums == list(range(1, len(layers) + 1))

    def test_depths_non_decreasing(self, layers):
        tops = [l["depth_top"] for l in layers]
        assert all(tops[i] <= tops[i+1] for i in range(len(tops)-1))


# ─────────────────────────────────────────────────────────────
# Module 7: AquiferDetector
# ─────────────────────────────────────────────────────────────

class TestAquiferDetector:

    def test_aquifer_found_in_sedimentary(self, aquifer_result):
        assert aquifer_result["aquifer_found"] is True

    def test_primary_aquifer_keys(self, aquifer_result):
        if aquifer_result["aquifer_found"]:
            pa = aquifer_result["primary_aquifer"]
            for k in ["lithology", "depth_top", "depth_bottom",
                      "thickness", "resistivity", "yield_label"]:
                assert k in pa

    def test_depth_bottom_not_none(self, aquifer_result):
        """The bug that was fixed — depth_bottom must never be None."""
        if aquifer_result["aquifer_found"]:
            for zone in aquifer_result["aquifer_zones"]:
                assert zone["depth_bottom"] is not None
                assert isinstance(zone["depth_bottom"], (int, float))

    def test_rec_depth_computable(self, aquifer_result):
        """rec_depth = depth_bottom + 5 must not crash."""
        if aquifer_result["aquifer_found"]:
            pa = aquifer_result["primary_aquifer"]
            depth_bot = pa["depth_bottom"] if pa["depth_bottom"] is not None \
                        else pa["depth_top"] + pa["thickness"]
            rec_depth = depth_bot + 5
            assert rec_depth > pa["depth_top"]

    def test_zones_sorted_by_score(self, aquifer_result):
        if len(aquifer_result["aquifer_zones"]) > 1:
            scores = [z["score"] for z in aquifer_result["aquifer_zones"]]
            assert scores == sorted(scores, reverse=True)

    def test_no_aquifer_scenario(self):
        """All clay layers → no aquifer found."""
        det = AquiferDetector()
        clay_layers = [
            {"layer_num": i+1, "name": "Clay", "is_aquifer": False,
             "rho": 15, "depth_top": i*5, "thickness": 5,
             "depth_bot": (i+1)*5, "color": "#708090"}
            for i in range(4)
        ]
        result = det.detect(clay_layers, "sedimentary")
        assert result["aquifer_found"] is False
        assert result["primary_aquifer"] is None


# ─────────────────────────────────────────────────────────────
# Module 8: DarZarouk
# ─────────────────────────────────────────────────────────────

class TestDarZarouk:

    def test_result_keys(self, dz_result):
        for k in ["layer_params", "overburden_S", "total_T", "vulnerability"]:
            assert k in dz_result

    def test_T_formula(self, dz_result):
        """T = rho * h for each layer."""
        for lp in dz_result["layer_params"]:
            expected_T = lp["rho"] * lp["thickness"]
            assert abs(lp["T"] - expected_T) < 1e-6

    def test_S_formula(self, dz_result):
        """S = h / rho for each layer."""
        for lp in dz_result["layer_params"]:
            expected_S = lp["thickness"] / lp["rho"]
            assert abs(lp["S"] - expected_S) < 1e-6

    def test_overburden_S_positive(self, dz_result):
        assert dz_result["overburden_S"] >= 0

    def test_total_T_positive(self, dz_result):
        assert dz_result["total_T"] > 0

    def test_vulnerability_label_valid(self, dz_result):
        valid_labels = {"GOOD", "MODERATE", "POOR", "EXTREMELY POOR"}
        assert dz_result["vulnerability"]["label"] in valid_labels

    def test_vulnerability_thresholds(self):
        dz = DarZarouk()
        mock_aq = {"aquifer_found": False}
        mock_layers = [
            {"layer_num": 1, "name": "Clay", "is_aquifer": False,
             "rho": 10, "depth_top": 0, "thickness": 100,
             "depth_bot": 100, "color": "#708090"}
        ]
        result = dz.compute(mock_layers, mock_aq)
        # S = 100/10 = 10.0 → should be GOOD
        assert result["vulnerability"]["label"] == "GOOD"
