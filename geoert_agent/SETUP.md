# GeoERT Agent — VS Code Setup Guide

Complete step-by-step instructions for setting up the project in VS Code from scratch.

---

## Step 1 — Clone or Download the Project

**Option A: Clone from GitHub (recommended)**
```bash
git clone https://github.com/yourusername/geoert-agent.git
cd geoert-agent
```

**Option B: Download ZIP**
1. Click **Code → Download ZIP** on GitHub
2. Extract to a folder, e.g. `C:\Users\Imran\Projects\geoert-agent`
3. Open your terminal and `cd` into that folder

---

## Step 2 — Open in VS Code

```bash
code .
```
Or: **File → Open Folder** and select the `geoert-agent` folder.

VS Code will detect `.vscode/extensions.json` and offer to install recommended extensions — click **Install All**.

---

## Step 3 — Create a Virtual Environment

A virtual environment keeps this project's packages separate from your system Python.

**Windows (Command Prompt or PowerShell):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt.

---

## Step 4 — Select the Python Interpreter in VS Code

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type: `Python: Select Interpreter`
3. Choose the one that shows `./venv/bin/python` or `.\venv\Scripts\python.exe`

---

## Step 5 — Install Dependencies

```bash
pip install -r requirements.txt
```

For development (includes testing and linting tools):
```bash
pip install -r requirements-dev.txt
```

Verify the installation:
```bash
python -c "import numpy, pandas, matplotlib, scipy; print('All OK')"
```

---

## Step 6 — Set Up Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in your Telegram bot token (only needed for bot deployment):
```
TELEGRAM_TOKEN=your_actual_token_from_botfather
```

---

## Step 7 — Run the Demo

**From the terminal:**
```bash
python run.py --demo --array schlumberger --terrain sedimentary
```

**From VS Code debugger:**
1. Press `F5` or click **Run → Start Debugging**
2. Select `🌍 Run Demo (Schlumberger · Sedimentary)` from the dropdown
3. Watch the output in the integrated terminal

---

## Step 8 — Run the Tests

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_all_modules.py::TestSampleDataGenerator::test_schlumberger_shape PASSED
tests/test_all_modules.py::TestERTCalculator::test_schlumberger_adds_columns PASSED
...
================================ XX passed in X.XXs =================================
```

---

## Step 9 — Run Your Own Field Data

Edit `run.py` directly, or use the command line:

```bash
python run.py \
  --file path/to/your_data.csv \
  --array schlumberger \
  --terrain sedimentary \
  --site "Your Site Name" \
  --output ./results
```

Or from Python:
```python
from geoert import GeoERTAgent
import pandas as pd

agent = GeoERTAgent()
result = agent.run(
    df         = pd.read_csv("your_data.csv"),
    array_type = "schlumberger",
    terrain    = "sedimentary",
    site_name  = "Kano Basin VES-01",
    save_dir   = "./results"
)
```

---

## Step 10 — Deploy the Telegram Bot (optional)

1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the token into your `.env` file
3. Install the bot library: `pip install python-telegram-bot`
4. Run: `python run.py --bot`

Or use the VS Code debugger: select `🤖 Start Telegram Bot` and press F5.

---

## Project Structure Reminder

```
geoert-agent/
│
├── geoert/                    ← The Python package (import from here)
│   ├── __init__.py            ← Exposes all classes
│   ├── agent.py               ← GeoERTAgent (full pipeline)
│   ├── ert_calculator.py      ← ERTCalculator
│   ├── curve_type.py          ← CurveTypeClassifier
│   ├── inversion.py           ← Inversion1D
│   ├── terrain_classifier.py  ← TerrainClassifier
│   ├── aquifer_detector.py    ← AquiferDetector
│   ├── dar_zarouk.py          ← DarZarouk
│   ├── visualizer.py          ← Visualizer
│   └── sample_data.py         ← SampleDataGenerator
│
├── bot/
│   └── telegram_bot.py        ← Telegram FSM bot
│
├── data/sample_data/          ← CSV test files
├── tests/                     ← pytest test suite
├── .vscode/                   ← VS Code config (shared)
│   ├── settings.json          ← Editor settings
│   ├── launch.json            ← Debug configurations (F5 menu)
│   └── extensions.json        ← Recommended extensions
│
├── run.py                     ← Command-line entry point
├── setup.py                   ← pip install -e . support
├── requirements.txt           ← Runtime dependencies
├── requirements-dev.txt       ← Dev/test dependencies
├── .env.example               ← Environment variable template
├── .gitignore
├── README.md
└── SETUP.md                   ← This file
```

---

## Common Issues

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'geoert'` | Make sure you're in the project root and venv is activated |
| `ModuleNotFoundError: No module named 'telegram'` | Run `pip install python-telegram-bot` |
| Plots don't appear | Run `import matplotlib; matplotlib.use('TkAgg')` or use Jupyter |
| Bot doesn't respond | Check `TELEGRAM_TOKEN` in `.env` is correct |
| Tests fail with import errors | Run `pip install -r requirements-dev.txt` |

---

## Useful VS Code Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Run / Debug with current launch config |
| `Ctrl+Shift+P` | Command palette |
| `Ctrl+`` ` | Open integrated terminal |
| `Ctrl+Shift+E` | File explorer |
| `Ctrl+Shift+G` | Git panel |
| `Ctrl+Shift+X` | Extensions panel |
| `Ctrl+.` | Quick fix / suggestions |
| `F12` | Go to definition |
| `Shift+F12` | Find all references |
