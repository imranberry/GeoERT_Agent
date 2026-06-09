# Sample Data Files

Synthetic ERT field data generated from a known 4-layer earth model for testing and validation.

## Files

| File | Array | Terrain | Rows |
|------|-------|---------|------|
| `schlumberger_sedimentary.csv` | Schlumberger | Sedimentary | 20 |
| `wenner_basement.csv` | Wenner | Basement Complex | 18 |
| `dipole_dipole_sedimentary.csv` | Dipole-Dipole | Sedimentary | 15 |

## Column Descriptions

### Schlumberger (`schlumberger_sedimentary.csv`)
| Column | Unit | Description |
|--------|------|-------------|
| `AB_2` | m | Half current electrode spacing (AB/2) |
| `MN_2` | m | Half potential electrode spacing (MN/2) |
| `Voltage_mV` | mV | Measured potential difference |
| `Current_mA` | mA | Injected current |

### Wenner (`wenner_basement.csv`)
| Column | Unit | Description |
|--------|------|-------------|
| `a_spacing` | m | Electrode spacing |
| `n_factor` | — | Separation factor (always 1 for Wenner) |
| `Voltage_mV` | mV | Measured potential difference |
| `Current_mA` | mA | Injected current |

### Dipole-Dipole (`dipole_dipole_sedimentary.csv`)
| Column | Unit | Description |
|--------|------|-------------|
| `a_spacing` | m | Dipole length |
| `n_factor` | — | Separation factor (1, 2, 3...) |
| `Voltage_mV` | mV | Measured potential difference |
| `Current_mA` | mA | Injected current |

## True Earth Model (used to generate these files)

**Sedimentary:**
```
Layer 1  | 120 Ω·m  |  3m  | Topsoil
Layer 2  |  15 Ω·m  |  8m  | Clay (confining)
Layer 3  | 350 Ω·m  | 12m  | Sand & Gravel AQUIFER
Layer 4  | 2500 Ω·m |  ∞   | Limestone bedrock
```

**Basement Complex:**
```
Layer 1  |   80 Ω·m |  4m  | Lateritic Topsoil
Layer 2  |   45 Ω·m | 10m  | Weathered Basement (aquifer)
Layer 3  |  650 Ω·m |  8m  | Fractured Basement (aquifer)
Layer 4  | 8000 Ω·m |  ∞   | Fresh Basement
```
