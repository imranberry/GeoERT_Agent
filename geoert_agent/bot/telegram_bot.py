"""
GeoERT Agent — Telegram Bot
============================
FSM conversation handler that accepts ERT field data (CSV or Excel),
runs the full interpretation pipeline, and returns:

  1. Annotated log-log plot (PNG)
  2. 2D layer model / borehole diagram (PNG)
  3. 3D borehole model (PNG)
  4. Combined dashboard (PNG)
  5. Updated data file with apparent resistivity added (CSV)
  6. Dar-Zarouk parameters table (Excel)
  7. Full summary report (text message)
"""

import os
import logging
import tempfile
import pandas as pd
import numpy as np
from io import StringIO, BytesIO
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# ── Import GeoERT modules ──────────────────────────────────────────────────
from geoert.agent import GeoERTAgent
from geoert.sample_data import SampleDataGenerator

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ── Conversation states ────────────────────────────────────────────────────
ARRAY_TYPE, TERRAIN_TYPE, SITE_NAME, UPLOAD_DATA = range(4)

ARRAY_KEYBOARD   = [["Schlumberger", "Wenner", "Dipole-Dipole"]]
TERRAIN_KEYBOARD = [["Sedimentary", "Basement Complex"]]

ARRAY_MAP   = {"Schlumberger": "schlumberger", "Wenner": "wenner", "Dipole-Dipole": "dipole_dipole"}
TERRAIN_MAP = {"Sedimentary": "sedimentary", "Basement Complex": "basement"}


# ══════════════════════════════════════════════════════════════════════════
# OUTPUT BUILDERS
# ══════════════════════════════════════════════════════════════════════════

def build_annotated_csv(ert_df: pd.DataFrame) -> bytes:
    """
    Return the field data CSV with apparent resistivity (rho_a) and
    geometric factor (K) appended as new columns.
    """
    cols = [c for c in ert_df.columns if c != "array"]
    out  = ert_df[cols].copy()
    out  = out.round(4)
    return out.to_csv(index=False).encode()


def build_dar_zarouk_excel(layers: list, dz_result: dict,
                            aquifer_result: dict, site_name: str) -> bytes:
    """
    Build a multi-sheet Excel workbook containing:
      Sheet 1 — Layer Model          (resistivity, thickness, lithology)
      Sheet 2 — Dar-Zarouk Parameters (T, S per layer + totals)
      Sheet 3 — Aquifer Summary       (zone details + recommendation)
    """
    buf = BytesIO()

    # ── Sheet 1: Layer Model ────────────────────────────────────────────
    layer_rows = []
    for l in layers:
        layer_rows.append({
            "Layer #":        l["layer_num"],
            "Lithology":      l["name"],
            "Resistivity (Ω·m)": round(l["rho"], 2),
            "Thickness (m)":  round(l["thickness"], 2) if l["thickness"] else "∞",
            "Top Depth (m)":  round(l["depth_top"], 2),
            "Bottom Depth (m)": round(l["depth_bot"], 2) if l.get("depth_bot") else "∞",
            "Aquifer?":       "YES" if l["is_aquifer"] else "No",
            "Confidence":     l.get("confidence", "—"),
            "Depth Rule Applied": "YES" if l.get("depth_rule_applied") else "No",
        })
    df_layers = pd.DataFrame(layer_rows)

    # ── Sheet 2: Dar-Zarouk Parameters ─────────────────────────────────
    dz_rows = []
    for lp in dz_result["layer_params"]:
        role = ("AQUIFER"    if lp["is_aquifer"] else
                "OVERBURDEN" if lp["is_overburden"] else "Substrate")
        dz_rows.append({
            "Layer #":               lp["layer_num"],
            "Lithology":             lp["lithology"],
            "Resistivity (Ω·m)":     round(lp["rho"], 2),
            "Thickness (m)":         round(lp["thickness"], 2),
            "Top Depth (m)":         round(lp["depth_top"], 2),
            "Transverse Resistance T (Ω·m²)":   round(lp["T"], 3),
            "Longitudinal Conductance S (S)":    round(lp["S"], 6),
            "Role":                  role,
        })
    df_dz = pd.DataFrame(dz_rows)

    # Totals row
    totals = pd.DataFrame([{
        "Layer #":               "TOTAL",
        "Lithology":             "—",
        "Resistivity (Ω·m)":     "—",
        "Thickness (m)":         "—",
        "Top Depth (m)":         "—",
        "Transverse Resistance T (Ω·m²)":  round(dz_result["total_T"], 3),
        "Longitudinal Conductance S (S)":   round(dz_result["overburden_S"], 6),
        "Role":                  "Overburden ΣS",
    }])
    df_dz = pd.concat([df_dz, totals], ignore_index=True)

    # ── Sheet 3: Aquifer Summary ────────────────────────────────────────
    aq = aquifer_result
    v  = dz_result["vulnerability"]

    if aq["aquifer_found"]:
        aq_rows = []
        for i, zone in enumerate(aq["aquifer_zones"]):
            d_bot = zone["depth_bottom"] if zone["depth_bottom"] is not None \
                    else zone["depth_top"] + zone["thickness"]
            aq_rows.append({
                "Rank":               i + 1,
                "Lithology":          zone["lithology"],
                "Top Depth (m)":      round(zone["depth_top"], 2),
                "Bottom Depth (m)":   round(d_bot, 2),
                "Thickness (m)":      round(zone["thickness"], 2),
                "Resistivity (Ω·m)":  round(zone["resistivity"], 2),
                "Yield Potential":    zone["yield_label"],
                "Contrast Ratio":     zone["contrast_ratio"],
                "Score":              round(zone["score"], 4),
            })
        df_aq = pd.DataFrame(aq_rows)

        pa    = aq["primary_aquifer"]
        d_bot = pa["depth_bottom"] if pa["depth_bottom"] is not None \
                else pa["depth_top"] + pa["thickness"]
        rec_depth = d_bot + 5

        df_meta = pd.DataFrame([
            {"Parameter": "Site Name",                    "Value": site_name},
            {"Parameter": "Primary Aquifer Lithology",   "Value": pa["lithology"]},
            {"Parameter": "Primary Aquifer Top (m)",     "Value": round(pa["depth_top"], 2)},
            {"Parameter": "Primary Aquifer Bottom (m)",  "Value": round(d_bot, 2)},
            {"Parameter": "Primary Aquifer Thickness (m)","Value": round(pa["thickness"], 2)},
            {"Parameter": "Yield Potential",             "Value": pa["yield_label"]},
            {"Parameter": "Recommended Borehole Depth (m)", "Value": round(rec_depth, 0)},
            {"Parameter": "Total Transverse Resistance T (Ω·m²)", "Value": round(dz_result["total_T"], 2)},
            {"Parameter": "Overburden Longitudinal Conductance S (S)", "Value": round(dz_result["overburden_S"], 6)},
            {"Parameter": "Contamination Vulnerability", "Value": v["label"]},
            {"Parameter": "Vulnerability Description",   "Value": v["desc"]},
        ])
    else:
        df_aq  = pd.DataFrame([{"Note": "No aquifer detected in the survey depth range."}])
        df_meta = pd.DataFrame([
            {"Parameter": "Site Name",                   "Value": site_name},
            {"Parameter": "Aquifer Found",               "Value": "No"},
            {"Parameter": "Recommendation",              "Value": "Consider deeper VES or alternative siting."},
            {"Parameter": "Contamination Vulnerability", "Value": v["label"]},
        ])

    # ── Write to Excel ──────────────────────────────────────────────────
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_layers.to_excel(writer, sheet_name="Layer Model",          index=False)
        df_dz.to_excel(    writer, sheet_name="Dar-Zarouk Parameters", index=False)
        df_aq.to_excel(    writer, sheet_name="Aquifer Zones",         index=False)
        df_meta.to_excel(  writer, sheet_name="Summary",               index=False)

        # ── Auto-fit column widths ──────────────────────────────────────
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value),
                    default=10
                )
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    return buf.getvalue()


def build_summary_text(site_name: str, array_type: str, terrain: str,
                        inv_result: dict, layers: list,
                        aquifer_result: dict, dz_result: dict,
                        curve_info: dict) -> str:
    """Build the complete plain-text summary report sent as a Telegram message."""

    aq = aquifer_result
    dz = dz_result
    v  = dz["vulnerability"]

    # ── Curve type ────────────────────────────────────────────
    ct_name = curve_info.get("name", curve_info.get("curve_type", "Unknown"))
    ct_info = curve_info.get("info", {})
    ct_hydro = ct_info.get("hydro", "")

    # ── Layer table ───────────────────────────────────────────
    layer_lines = []
    for l in layers:
        h   = f"{l['thickness']:.1f}m" if l["thickness"] else "∞"
        aq_tag = " 💧" if l["is_aquifer"] else ""
        layer_lines.append(
            f"  L{l['layer_num']}  {l['name']:<22} {l['rho']:>8.1f} Ω·m  {h:>7}  @{l['depth_top']:.1f}m{aq_tag}"
        )
    layer_table = "\n".join(layer_lines)

    # ── Dar-Zarouk table ──────────────────────────────────────
    dz_lines = []
    for lp in dz["layer_params"]:
        role = ("AQUIFER 💧" if lp["is_aquifer"] else
                "Overburden" if lp["is_overburden"] else "Substrate")
        dz_lines.append(
            f"  L{lp['layer_num']}  T={lp['T']:>10.1f} Ω·m²  S={lp['S']:.5f} S  [{role}]"
        )
    dz_table = "\n".join(dz_lines)

    # ── Aquifer section ───────────────────────────────────────
    if aq["aquifer_found"]:
        pa    = aq["primary_aquifer"]
        d_bot = pa["depth_bottom"] if pa["depth_bottom"] is not None \
                else pa["depth_top"] + pa["thickness"]
        rec   = d_bot + 5

        aq_lines = [f"  ★ {pa['lithology']}"]
        aq_lines.append(f"    Depth     : {pa['depth_top']:.1f}m – {d_bot:.1f}m")
        aq_lines.append(f"    Thickness : {pa['thickness']:.1f}m")
        aq_lines.append(f"    ρ         : {pa['resistivity']:.1f} Ω·m")
        aq_lines.append(f"    Yield     : {pa['yield_label']} — {pa['yield_desc']}")
        aq_lines.append(f"    Rec. depth: ≥ {rec:.0f}m below surface")

        if len(aq["aquifer_zones"]) > 1:
            aq_lines.append(f"\n  Other zones detected: {len(aq['aquifer_zones']) - 1}")

        aq_section = "\n".join(aq_lines)
    else:
        aq_section = "  ⚠️  No viable aquifer detected.\n  Consider deeper VES or re-siting."

    # ── RMS fit ───────────────────────────────────────────────
    rms = inv_result.get("rms_error", 0)
    fit = "Excellent" if rms < 0.1 else "Good" if rms < 0.3 else "Fair" if rms < 0.6 else "Poor"

    # ── Assemble ──────────────────────────────────────────────
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🌍  GeoERT INTERPRETATION REPORT",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Site    : {site_name}",
        f"Array   : {array_type.title()}",
        f"Terrain : {terrain.title()}",
        "",
        "─── VES CURVE TYPE ─────────────────",
        f"  Type    : {ct_name}",
        f"  Meaning : {ct_hydro}" if ct_hydro else "",
        "",
        "─── INVERTED LAYER MODEL ───────────",
        f"  Inversion fit : {fit} (RMS = {rms:.4f})",
        layer_table,
        "",
        "─── DAR-ZAROUK PARAMETERS ──────────",
        dz_table,
        f"  ΣT (total)           = {dz['total_T']:.2f} Ω·m²",
        f"  ΣS (overburden)      = {dz['overburden_S']:.6f} S",
        "",
        "─── CONTAMINATION VULNERABILITY ────",
        f"  {v['icon']}  {v['label']}",
        f"  {v['desc']}",
        "",
        "─── AQUIFER DETECTION ──────────────",
        aq_section,
        "",
        "─── FILES ATTACHED ─────────────────",
        "  📊 dashboard.png        — 4-panel interpretation",
        "  🕳️  borehole_3d.png      — 3D layer cylinder",
        "  📈 loglog_annotated.png  — VES curve + curve type",
        "  📄 data_with_rho_a.csv  — your data + ρₐ + K columns",
        "  📋 dar_zarouk_report.xlsx — full parameter tables",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "GeoERT Agent | Codar Data Science",
    ]

    return "\n".join(l for l in lines if l is not None)


# ══════════════════════════════════════════════════════════════════════════
# CONVERSATION HANDLERS
# ══════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *Welcome to GeoERT Agent*\n\n"
        "I will interpret your ERT geophysical survey and return:\n"
        "• Interpretation plots (log-log, layer model, 3D borehole)\n"
        "• Your data file with apparent resistivity added\n"
        "• Dar-Zarouk parameter tables (Excel)\n"
        "• Full text summary report\n\n"
        "*What electrode array did you use?*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(ARRAY_KEYBOARD, one_time_keyboard=True,
                                         resize_keyboard=True),
    )
    return ARRAY_TYPE


async def get_array_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in ARRAY_MAP:
        await update.message.reply_text("Please tap one of the buttons below.",
                                         reply_markup=ReplyKeyboardMarkup(ARRAY_KEYBOARD,
                                         one_time_keyboard=True, resize_keyboard=True))
        return ARRAY_TYPE

    context.user_data["array_type"] = ARRAY_MAP[text]
    await update.message.reply_text(
        "*What is the terrain type of your survey area?*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(TERRAIN_KEYBOARD, one_time_keyboard=True,
                                          resize_keyboard=True),
    )
    return TERRAIN_TYPE


async def get_terrain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in TERRAIN_MAP:
        await update.message.reply_text("Please tap one of the buttons below.",
                                         reply_markup=ReplyKeyboardMarkup(TERRAIN_KEYBOARD,
                                         one_time_keyboard=True, resize_keyboard=True))
        return TERRAIN_TYPE

    context.user_data["terrain"] = TERRAIN_MAP[text]
    await update.message.reply_text(
        "*What is the site or location name?*\n"
        "_(e.g. Kano Basin — VES Station 01)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SITE_NAME


async def get_site_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["site_name"] = update.message.text
    array_type = context.user_data["array_type"]

    fmt_map = {
        "schlumberger":  "`AB_2, MN_2, Voltage_mV, Current_mA`",
        "wenner":        "`a_spacing, n_factor, Voltage_mV, Current_mA`",
        "dipole_dipole": "`a_spacing, n_factor, Voltage_mV, Current_mA`",
    }

    await update.message.reply_text(
        f"📂 *Upload your ERT data file.*\n\n"
        f"Accepted formats: *CSV* or *Excel (.xlsx)*\n"
        f"Required columns: {fmt_map[array_type]}\n\n"
        f"_Data must be on Sheet 1 if using Excel._",
        parse_mode="Markdown",
    )
    return UPLOAD_DATA


async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main processing handler. Downloads the file, runs the full GeoERT
    pipeline, then sends back all output files and the summary report.
    """
    await update.message.reply_text("⚙️ Processing your data — this takes about 20 seconds…")

    try:
        # ── 1. Download and read the uploaded file ──────────────────────
        tg_file   = await update.message.document.get_file()
        file_bytes = await tg_file.download_as_bytearray()
        file_name  = update.message.document.file_name.lower()

        if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
            df = pd.read_excel(BytesIO(file_bytes))
        elif file_name.endswith(".csv"):
            df = pd.read_csv(StringIO(file_bytes.decode()))
        else:
            await update.message.reply_text(
                "❌ Unsupported file type. Please upload a *.csv* or *.xlsx* file.",
                parse_mode="Markdown",
            )
            return UPLOAD_DATA

        array_type = context.user_data["array_type"]
        terrain    = context.user_data["terrain"]
        site_name  = context.user_data.get("site_name", "Survey Site")
        user_id    = update.effective_user.id

        # ── 2. Run the full GeoERT pipeline ────────────────────────────
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent  = GeoERTAgent()
            result = agent.run(
                df         = df,
                array_type = array_type,
                terrain    = terrain,
                site_name  = site_name,
                save_dir   = tmp_dir,
            )

            ert_df        = result["ert_df"]
            inv_result    = result["inv_result"]
            layers        = result["layers"]
            aquifer_result = result["aquifer_result"]
            dz_result     = result["dz_result"]
            curve_info    = result.get("apparent_curve_type", {})

            # ── 3. Build output files ───────────────────────────────────

            # a) Annotated CSV (original data + rho_a + K)
            csv_bytes = build_annotated_csv(ert_df)

            # b) Dar-Zarouk Excel workbook (4 sheets)
            xlsx_bytes = build_dar_zarouk_excel(
                layers, dz_result, aquifer_result, site_name
            )

            # c) Text summary
            summary = build_summary_text(
                site_name, array_type, terrain,
                inv_result, layers, aquifer_result, dz_result, curve_info
            )

            # ── 4. Send all outputs to Telegram ────────────────────────

            # Plot 1 — Annotated log-log curve
            loglog_path = os.path.join(tmp_dir, "loglog_annotated.png")
            if os.path.exists(loglog_path):
                with open(loglog_path, "rb") as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption="📈 *VES Log-Log Curve* — curve type annotated",
                        parse_mode="Markdown",
                    )

            # Plot 2 — Dashboard
            dashboard_path = os.path.join(tmp_dir, "dashboard.png")
            if os.path.exists(dashboard_path):
                with open(dashboard_path, "rb") as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption="📊 *Interpretation Dashboard* — layer model · Dar-Zarouk · aquifer",
                        parse_mode="Markdown",
                    )

            # Plot 3 — 3D Borehole
            borehole_path = os.path.join(tmp_dir, "borehole_3d.png")
            if os.path.exists(borehole_path):
                with open(borehole_path, "rb") as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption="🕳️ *3D Borehole Model*",
                        parse_mode="Markdown",
                    )

            # File 4 — Annotated CSV
            await update.message.reply_document(
                document=BytesIO(csv_bytes),
                filename=f"data_with_rho_a_{site_name.replace(' ', '_')}.csv",
                caption=(
                    "📄 *Your data + apparent resistivity*\n"
                    "New columns added: `rho_a` (Ω·m), `K` (geometric factor), `spacing`"
                ),
                parse_mode="Markdown",
            )

            # File 5 — Dar-Zarouk Excel workbook
            await update.message.reply_document(
                document=BytesIO(xlsx_bytes),
                filename=f"dar_zarouk_{site_name.replace(' ', '_')}.xlsx",
                caption=(
                    "📋 *Dar-Zarouk Report (Excel)*\n"
                    "4 sheets: Layer Model · Dar-Zarouk Parameters · Aquifer Zones · Summary"
                ),
                parse_mode="Markdown",
            )

            # Message 6 — Full text summary
            await update.message.reply_text(summary, parse_mode="Markdown")

        logger.info("Completed processing for user %s — site: %s", user_id, site_name)

    except KeyError as e:
        await update.message.reply_text(
            f"❌ *Column not found:* `{e}`\n\n"
            f"Check that your file has the correct column names for the "
            f"*{context.user_data.get('array_type', 'chosen')}* array.",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("Pipeline error for user %s", update.effective_user.id)
        await update.message.reply_text(
            f"❌ *Error during processing:*\n`{str(e)}`\n\n"
            "Please check your data format and try again. "
            "Send /start to begin a new session.",
            parse_mode="Markdown",
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Session cancelled. Send /start whenever you are ready.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *GeoERT Agent — Help*\n\n"
        "*Commands:*\n"
        "/start — begin a new interpretation session\n"
        "/cancel — cancel the current session\n"
        "/help — show this message\n\n"
        "*Supported file formats:* CSV, Excel (.xlsx)\n\n"
        "*Column names required:*\n"
        "• Schlumberger: `AB_2, MN_2, Voltage_mV, Current_mA`\n"
        "• Wenner: `a_spacing, n_factor, Voltage_mV, Current_mA`\n"
        "• Dipole-Dipole: `a_spacing, n_factor, Voltage_mV, Current_mA`\n\n"
        "*What you get back:*\n"
        "• VES log-log curve (PNG)\n"
        "• Interpretation dashboard (PNG)\n"
        "• 3D borehole model (PNG)\n"
        "• Data file with ρₐ and K added (CSV)\n"
        "• Dar-Zarouk parameter report (Excel)\n"
        "• Full text summary with aquifer recommendation",
        parse_mode="Markdown",
    )


# ══════════════════════════════════════════════════════════════════════════
# MAIN — BOT STARTUP
# ══════════════════════════════════════════════════════════════════════════

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError(
            "TELEGRAM_TOKEN not set. Add it to your .env file:\n"
            "TELEGRAM_TOKEN=your_token_here"
        )

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ARRAY_TYPE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_array_type)],
            TERRAIN_TYPE:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_terrain)],
            SITE_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_site_name)],
            UPLOAD_DATA: [MessageHandler(filters.Document.ALL, process_file)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start",  start),
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))

    print("🤖 GeoERT Bot is running — press Ctrl+C to stop")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
