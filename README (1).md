#  GeoERT Agent

> **AI-powered Electrical Resistivity Tomography (ERT) interpretation system — from raw field data to full geological report in under 30 seconds, deployable as a Telegram bot.**

---

## 📌 What It Does

GeoERT Agent accepts raw **Vertical Electrical Sounding (VES)** field data from any standard electrode array and returns a complete geological interpretation — no software installation, no consultant, no waiting. Just upload your data file and get your report.

**Try it now:** Search `@GeoERT_bot` on Telegram → send `/start`

---

## ✅ Key Features

| Feature | Detail |
|---|---|
| **Multi-array support** | Schlumberger · Wenner · Dipole-Dipole |
| **VES curve type identification** | A · Q · H · K · HA · HK · KH · KQ · AA · QQ |
| **1D Inversion** | L-BFGS-B optimiser with Occam smoothness regularisation |
| **Depth-aware layer classification** | First 0–5m enforced as overburden regardless of resistivity |
| **Terrain intelligence** | Separate rule sets for sedimentary basin and basement complex |
| **Aquifer detection & ranking** | Yield potential (Very High → Low) + recommended borehole depth |
| **Dar-Zarouk parameters** | Transverse resistance T, longitudinal conductance S, anisotropy λ |
| **Contamination vulnerability** | 4-tier assessment per Oladapo & Akintorinwa (2007) |
| **File support** | CSV and Excel (.xlsx) upload |
| **6 outputs per session** | 3 plots + annotated CSV + Excel report + text summary |

---

## 📤 What You Get Back

Every session returns 6 outputs directly in Telegram:

```
📈  loglog_annotated.png     — VES curve with curve type annotation
📊  dashboard.png             — 4-panel interpretation dashboard
🕳️  borehole_3d.png           — 3D cylindrical layer model
📄  data_with_rho_a.csv       — your original data + ρₐ, K, spacing columns
📋  dar_zarouk_report.xlsx    — 4-sheet Excel: Layer Model · Dar-Zarouk · Aquifer Zones · Summary
📝  Text report               — full interpretation with aquifer recommendation
```

---

## 📋 Data Input Format

Upload a **CSV or Excel (.xlsx)** file. Row 1 must be the column headers — no title rows above.

### Schlumberger Array

| Column | Unit | Description |
|--------|------|-------------|
| `AB_2` | m | Half current electrode spacing (AB/2) |
| `MN_2` | m | Half potential electrode spacing (MN/2) |
| `Voltage_mV` | mV | Measured potential difference |
| `Current_mA` | mA | Injected current (typically 100 mA) |

**Example:**
```csv
AB_2,MN_2,Voltage_mV,Current_mA
1.0,0.500,15690.0,100.0
2.0,0.499,5720.0,100.0
3.0,0.500,2360.0,100.0
6.0,0.501,880.0,100.0
10.0,0.997,1800.0,100.0
15.0,2.508,2600.0,100.0
20.0,2.504,1700.0,100.0
30.0,2.498,900.0,100.0
40.0,7.507,600.0,100.0
50.0,7.497,600.0,100.0
```

### Wenner / Dipole-Dipole Array

| Column | Unit | Description |
|--------|------|-------------|
| `a_spacing` | m | Electrode spacing |
| `n_factor` | — | Separation factor (always 1 for Wenner; 1, 2, 3... for Dipole-Dipole) |
| `Voltage_mV` | mV | Measured potential difference |
| `Current_mA` | mA | Injected current |

**Example:**
```csv
a_spacing,n_factor,Voltage_mV,Current_mA
2.0,1.0,520.0,100.0
3.0,1.0,415.0,100.0
5.0,1.0,310.0,100.0
10.0,1.0,185.0,100.0
10.0,2.0,98.0,100.0
10.0,3.0,54.0,100.0
```

> ⚠️ **Rules:** Column names are case-sensitive. All values must be numbers. No empty cells. For Excel: data must be on Sheet 1.

---

## 🔬 Geophysical Methods

### Apparent Resistivity

| Array | Geometric Factor K | Formula |
|---|---|---|
| Schlumberger | K = π(AB² − MN²) / (2 · MN/2) | ρₐ = K × ΔV / I |
| Wenner | K = 2πa | ρₐ = K × ΔV / I |
| Dipole-Dipole | K = πn(n+1)(n+2)a | ρₐ = K × ΔV / I |

### VES Curve Types

| Curve | Pattern | Hydrogeological Meaning |
|---|---|---|
| **H-type** | ρ₁ > ρ₂ < ρ₃ | Conductive middle layer — **classic aquifer indicator** |
| **K-type** | ρ₁ < ρ₂ > ρ₃ | Resistive middle — dry sand or fractured basement |
| **HA-type** | ρ₁ > ρ₂ < ρ₃ < ρ₄ | Aquifer over resistive basement — **excellent borehole target** |
| **A-type** | ρ₁ < ρ₂ < ρ₃ | Rising — increasing compaction toward bedrock |
| **Q-type** | ρ₁ > ρ₂ > ρ₃ | Falling — saline intrusion risk |
| **KH-type** | ρ₁ < ρ₂ > ρ₃ < ρ₄ | Resistive peak over aquifer zone |

### Dar-Zarouk Contamination Vulnerability

| Overburden S (Siemens) | Protection Level |
|---|---|
| S ≥ 10 | 🟢 **Good** — Well protected |
| 1 ≤ S < 10 | 🟡 **Moderate** — Some contamination risk |
| 0.1 ≤ S < 1 | 🟠 **Poor** — High contamination risk |
| S < 0.1 | 🔴 **Extremely Poor** — Aquifer fully exposed |

---

## 🏗️ Architecture

```
User (Telegram)
      │  CSV or Excel upload
      ▼
┌─────────────────────────────────┐
│         Telegram FSM Bot        │
│  /start → array → terrain →     │
│  site name → upload file        │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│         GeoERT Pipeline         │
│                                 │
│  ERTCalculator    → ρₐ + K      │
│  CurveTypeClass.  → H/K/A/Q...  │
│  Inversion1D      → layer model │
│  TerrainClassif.  → lithology   │
│  AquiferDetector  → yield+depth │
│  DarZarouk        → T, S, risk  │
│  Visualizer       → 5 plots     │
└──────────────┬──────────────────┘
               │
               ▼
     6 outputs sent to user
```

---

## 📁 Project Structure

```
geoert-agent/
│
├── geoert/                        ← Python package
│   ├── __init__.py
│   ├── agent.py                   ← GeoERTAgent (full pipeline)
│   ├── ert_calculator.py          ← Apparent resistivity + K
│   ├── curve_type.py              ← VES curve shape classifier
│   ├── inversion.py               ← 1D inversion engine
│   ├── terrain_classifier.py      ← Depth-aware lithology classification
│   ├── aquifer_detector.py        ← Aquifer zone detection
│   ├── dar_zarouk.py              ← T, S, λ + contamination vulnerability
│   ├── visualizer.py              ← All plots
│   └── sample_data.py             ← Synthetic test data generator
│
├── bot/
│   └── telegram_bot.py            ← Telegram FSM bot
│
├── data/sample_data/
│   ├── schlumberger_sedimentary.csv
│   ├── wenner_basement.csv
│   └── dipole_dipole_sedimentary.csv
│
├── tests/
│   └── test_all_modules.py        ← 30+ unit tests
│
├── requirements.txt
├── nixpacks.toml                  ← Railway build config
├── railway.toml                   ← Railway deploy config
├── Procfile
├── runtime.txt
├── .env.example
└── README.md
```

---

## 🚀 Deployment

### Run Locally

```bash
# 1. Clone
git clone https://github.com/yourusername/geoert-agent.git
cd geoert-agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your token
cp .env.example .env
# Edit .env: TELEGRAM_TOKEN=your_token_here

# 5. Start the bot
python bot/telegram_bot.py
```

### Deploy on Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Go to **Variables** tab → add `TELEGRAM_TOKEN` = your bot token
5. Railway auto-detects `nixpacks.toml` and deploys

> Get your bot token from [@BotFather](https://t.me/BotFather): send `/newbot` and follow the prompts.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 📦 Dependencies

```
numpy>=1.24.0          pandas>=1.5.0
matplotlib>=3.6.0      scipy>=1.10.0
python-telegram-bot>=20.0
python-dotenv>=1.0.0   openpyxl>=3.1.0
et-xmlfile>=1.1.0
```

---

## 📚 Scientific References

- Koefoed, O. (1979). *Geosounding Principles.* Elsevier.
- Telford, Geldart & Sheriff (1990). *Applied Geophysics (2nd ed.).* Cambridge University Press.
- Oladapo & Akintorinwa (2007). Hydrogeophysical study of Ogbese. *Global J. Pure & Applied Sciences, 13(1)*, 55–61.
- Niwas & Singhal (1981). Estimation of aquifer transmissivity from Dar-Zarrouk parameters. *Journal of Hydrology, 50*, 393–399.
- Reynolds, J.M. (2011). *An Introduction to Applied and Environmental Geophysics (2nd ed.).* Wiley-Blackwell.

---

## 🤝 Contributing

Contributions welcome — especially additional terrain catalogs, 2D profile support, PyGIMLi integration, and a web interface.

```bash
git checkout -b feature/your-feature
git commit -m "Add: description"
git push origin feature/your-feature
# Open a Pull Request
```

---

## 👤 Author

**Malik Oluwatobiloba Imran**
Data Science Instructor · [Codar Data Science Program](https://codar.ng) · Nigeria

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*If this project helped your research or borehole siting, please give it a ⭐*
