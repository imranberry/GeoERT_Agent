"""
GeoERT Agent — Railway Deployment Entry Point
==============================================
Railway runs: python bot/telegram_bot.py
This file is the direct entry point — no argparse, no run.py needed.
"""

import os
import sys
import logging

# ── Make sure the project root is on the path ─────────────────────────────
# When Railway runs "python bot/telegram_bot.py" from the repo root,
# the geoert/ package must be importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Verify token exists before importing telegram ─────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable is not set.")
    logger.error("Set it in Railway → your service → Variables tab.")
    sys.exit(1)

# ── Verify all required libraries are installed ───────────────────────────
missing = []
for lib in ["telegram", "numpy", "pandas", "matplotlib", "scipy", "openpyxl"]:
    try:
        __import__(lib)
    except ImportError:
        missing.append(lib)

if missing:
    logger.error("Missing libraries: %s", missing)
    logger.error("Check that requirements.txt is in the project root.")
    sys.exit(1)

logger.info("All libraries OK. Starting GeoERT bot...")

# ── Start the bot ─────────────────────────────────────────────────────────
import os
import logging
import tempfile
import pandas as pd
import numpy as np
from io import StringIO, BytesIO

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from geoert.agent import GeoERTAgent

# ── Conversation states ────────────────────────────────────────────────────
ARRAY_TYPE, TERRAIN_TYPE, SITE_NAME, UPLOAD_DATA = range(4)

ARRAY_KEYBOARD   = [["Schlumberger", "Wenner", "Dipole-Dipole"]]
TERRAIN_KEYBOARD = [["Sedimentary", "Basement Complex"]]
ARRAY_MAP        = {"Schlumberger": "schlumberger", "Wenner": "wenner",
                    "Dipole-Dipole": "dipole_dipole"}
TERRAIN_MAP      = {"Sedimentary": "sedimentary", "Basement Complex": "basement"}


# ══════════════════════════════════════════════════════════════════════════
# OUTPUT BUILDERS
# ══════════════════════════════════════════════════════════════════════════

def build_annotated_csv(ert_df: pd.DataFrame) -> bytes:
    cols = [c for c in ert_df.columns if c != "array"]
    return ert_df[cols].round(4).to_csv(index=False).encode()


def build_dar_zarouk_excel(layers, dz_result, aquifer_result, site_name) -> bytes:
    buf = BytesIO()
    aq  = aquifer_result
    v   = dz_result["vulnerability"]

    # Sheet 1 — Layer Model
    layer_rows = []
    for l in layers:
        layer_rows.append({
            "Layer #":           l["layer_num"],
            "Lithology":         l["name"],
            "Resistivity (Ohm·m)": round(l["rho"], 2),
            "Thickness (m)":     round(l["thickness"], 2) if l["thickness"] else "inf",
            "Top Depth (m)":     round(l["depth_top"], 2),
            "Bottom Depth (m)":  round(l["depth_bot"], 2) if l.get("depth_bot") else "inf",
            "Aquifer?":          "YES" if l["is_aquifer"] else "No",
            "Confidence":        l.get("confidence", "—"),
        })
    df_layers = pd.DataFrame(layer_rows)

    # Sheet 2 — Dar-Zarouk Parameters
    dz_rows = []
    for lp in dz_result["layer_params"]:
        role = ("AQUIFER"    if lp["is_aquifer"] else
                "OVERBURDEN" if lp["is_overburden"] else "Substrate")
        dz_rows.append({
            "Layer #":              lp["layer_num"],
            "Lithology":            lp["lithology"],
            "Resistivity (Ohm·m)":  round(lp["rho"], 2),
            "Thickness (m)":        round(lp["thickness"], 2),
            "Top Depth (m)":        round(lp["depth_top"], 2),
            "Transverse Resistance T (Ohm·m2)": round(lp["T"], 3),
            "Longitudinal Conductance S (S)":   round(lp["S"], 6),
            "Role":                 role,
        })
    df_dz = pd.DataFrame(dz_rows)
    totals = pd.DataFrame([{
        "Layer #": "TOTAL", "Lithology": "—",
        "Resistivity (Ohm·m)": "—", "Thickness (m)": "—", "Top Depth (m)": "—",
        "Transverse Resistance T (Ohm·m2)": round(dz_result["total_T"], 3),
        "Longitudinal Conductance S (S)":   round(dz_result["overburden_S"], 6),
        "Role": "Overburden sum",
    }])
    df_dz = pd.concat([df_dz, totals], ignore_index=True)

    # Sheet 3 — Aquifer Zones
    if aq["aquifer_found"]:
        aq_rows = []
        for i, zone in enumerate(aq["aquifer_zones"]):
            d_bot = zone["depth_bottom"] if zone["depth_bottom"] is not None \
                    else zone["depth_top"] + zone["thickness"]
            aq_rows.append({
                "Rank": i + 1,
                "Lithology":         zone["lithology"],
                "Top Depth (m)":     round(zone["depth_top"], 2),
                "Bottom Depth (m)":  round(d_bot, 2),
                "Thickness (m)":     round(zone["thickness"], 2),
                "Resistivity (Ohm·m)": round(zone["resistivity"], 2),
                "Yield Potential":   zone["yield_label"],
                "Contrast Ratio":    zone["contrast_ratio"],
            })
        df_aq = pd.DataFrame(aq_rows)
        pa    = aq["primary_aquifer"]
        d_bot = pa["depth_bottom"] if pa["depth_bottom"] is not None \
                else pa["depth_top"] + pa["thickness"]
        df_meta = pd.DataFrame([
            {"Parameter": "Site Name",                    "Value": site_name},
            {"Parameter": "Primary Aquifer",              "Value": pa["lithology"]},
            {"Parameter": "Depth Top (m)",                "Value": round(pa["depth_top"], 2)},
            {"Parameter": "Depth Bottom (m)",             "Value": round(d_bot, 2)},
            {"Parameter": "Thickness (m)",                "Value": round(pa["thickness"], 2)},
            {"Parameter": "Yield Potential",              "Value": pa["yield_label"]},
            {"Parameter": "Recommended Borehole Depth (m)", "Value": round(d_bot + 5, 0)},
            {"Parameter": "Total T (Ohm·m2)",             "Value": round(dz_result["total_T"], 2)},
            {"Parameter": "Overburden S (S)",             "Value": round(dz_result["overburden_S"], 6)},
            {"Parameter": "Contamination Vulnerability",  "Value": v["label"]},
            {"Parameter": "Description",                  "Value": v["desc"]},
        ])
    else:
        df_aq   = pd.DataFrame([{"Note": "No aquifer detected."}])
        df_meta = pd.DataFrame([
            {"Parameter": "Site Name",    "Value": site_name},
            {"Parameter": "Aquifer Found","Value": "No"},
            {"Parameter": "Vulnerability","Value": v["label"]},
        ])

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_layers.to_excel(writer, sheet_name="Layer Model",          index=False)
        df_dz.to_excel(    writer, sheet_name="Dar-Zarouk Parameters", index=False)
        df_aq.to_excel(    writer, sheet_name="Aquifer Zones",         index=False)
        df_meta.to_excel(  writer, sheet_name="Summary",               index=False)
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                w = max((len(str(c.value)) for c in col if c.value), default=10)
                sheet.column_dimensions[col[0].column_letter].width = min(w + 4, 40)

    return buf.getvalue()


def build_summary_text(site_name, array_type, terrain,
                       inv_result, layers, aquifer_result, dz_result,
                       curve_info) -> str:
    aq  = aquifer_result
    dz  = dz_result
    v   = dz["vulnerability"]
    ct  = curve_info.get("curve_type", "Unknown")
    ct_info = curve_info.get("info", {})
    hydro   = ct_info.get("hydro", "")

    layer_lines = []
    for l in layers:
        h  = f"{l['thickness']:.1f}m" if l["thickness"] else "inf"
        aq_tag = " *AQUIFER*" if l["is_aquifer"] else ""
        layer_lines.append(
            f"  L{l['layer_num']}  {l['name']:<20} {l['rho']:>8.1f} Ohm.m  "
            f"{h:>7}  @{l['depth_top']:.1f}m{aq_tag}"
        )

    dz_lines = []
    for lp in dz["layer_params"]:
        role = "AQUIFER" if lp["is_aquifer"] else ("Overburden" if lp["is_overburden"] else "Substrate")
        dz_lines.append(
            f"  L{lp['layer_num']}  T={lp['T']:>9.1f}  S={lp['S']:.5f}  [{role}]"
        )

    if aq["aquifer_found"]:
        pa    = aq["primary_aquifer"]
        d_bot = pa["depth_bottom"] if pa["depth_bottom"] is not None \
                else pa["depth_top"] + pa["thickness"]
        aq_section = (
            f"  * {pa['lithology']}\n"
            f"    Depth     : {pa['depth_top']:.1f}m to {d_bot:.1f}m\n"
            f"    Thickness : {pa['thickness']:.1f}m\n"
            f"    Yield     : {pa['yield_label']} — {pa['yield_desc']}\n"
            f"    Rec. depth: >= {d_bot + 5:.0f}m below surface"
        )
    else:
        aq_section = "  No viable aquifer detected.\n  Consider deeper VES or re-siting."

    rms = inv_result.get("rms_error", 0)
    fit = "Excellent" if rms < 0.1 else "Good" if rms < 0.3 else "Fair" if rms < 0.6 else "Poor"

    return "\n".join([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🌍  GeoERT INTERPRETATION REPORT",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Site    : {site_name}",
        f"Array   : {array_type.title()}",
        f"Terrain : {terrain.title()}",
        "",
        "─── VES CURVE TYPE ─────────────",
        f"  Type    : {ct}",
        f"  Meaning : {hydro}" if hydro else "",
        "",
        "─── INVERTED LAYER MODEL ───────",
        f"  Fit: {fit}  (RMS = {rms:.4f})",
        *layer_lines,
        "",
        "─── DAR-ZAROUK PARAMETERS ──────",
        *dz_lines,
        f"  Total T          = {dz['total_T']:.2f} Ohm.m2",
        f"  Overburden S     = {dz['overburden_S']:.6f} S",
        "",
        "─── CONTAMINATION RISK ─────────",
        f"  {v['icon']}  {v['label']}",
        f"  {v['desc']}",
        "",
        "─── AQUIFER ────────────────────",
        aq_section,
        "",
        "─── FILES ATTACHED ─────────────",
        "  Log-log curve PNG",
        "  Dashboard PNG",
        "  3D borehole PNG",
        "  Data + rho_a CSV",
        "  Dar-Zarouk Excel (4 sheets)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "GeoERT Agent | Codar Data Science",
    ])


# ══════════════════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *Welcome to GeoERT Agent*\n\n"
        "I interpret ERT geophysical surveys and return:\n"
        "• Interpretation plots\n"
        "• Your data with apparent resistivity added\n"
        "• Dar-Zarouk parameter tables (Excel)\n"
        "• Full text summary + aquifer recommendation\n\n"
        "*What electrode array did you use?*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            ARRAY_KEYBOARD, one_time_keyboard=True, resize_keyboard=True),
    )
    return ARRAY_TYPE


async def get_array_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in ARRAY_MAP:
        await update.message.reply_text(
            "Please tap one of the buttons.",
            reply_markup=ReplyKeyboardMarkup(
                ARRAY_KEYBOARD, one_time_keyboard=True, resize_keyboard=True))
        return ARRAY_TYPE
    context.user_data["array_type"] = ARRAY_MAP[text]
    await update.message.reply_text(
        "*What is the terrain type?*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            TERRAIN_KEYBOARD, one_time_keyboard=True, resize_keyboard=True),
    )
    return TERRAIN_TYPE


async def get_terrain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in TERRAIN_MAP:
        await update.message.reply_text(
            "Please tap one of the buttons.",
            reply_markup=ReplyKeyboardMarkup(
                TERRAIN_KEYBOARD, one_time_keyboard=True, resize_keyboard=True))
        return TERRAIN_TYPE
    context.user_data["terrain"] = TERRAIN_MAP[text]
    await update.message.reply_text(
        "*What is the site name?*\n_(e.g. Kano Basin — VES Station 01)_",
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
        f"📂 *Upload your ERT data file*\n\n"
        f"Accepted: *CSV* or *Excel (.xlsx)*\n"
        f"Columns needed: {fmt_map[array_type]}\n\n"
        f"_Excel: data must be on Sheet 1._",
        parse_mode="Markdown",
    )
    return UPLOAD_DATA


async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Processing your data — please wait about 20 seconds…")
    try:
        tg_file    = await update.message.document.get_file()
        file_bytes = await tg_file.download_as_bytearray()
        file_name  = update.message.document.file_name.lower()

        if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
            df = pd.read_excel(BytesIO(file_bytes))
        elif file_name.endswith(".csv"):
            df = pd.read_csv(StringIO(file_bytes.decode()))
        else:
            await update.message.reply_text(
                "❌ Unsupported file type. Please upload a *.csv* or *.xlsx* file.",
                parse_mode="Markdown")
            return UPLOAD_DATA

        array_type = context.user_data["array_type"]
        terrain    = context.user_data["terrain"]
        site_name  = context.user_data.get("site_name", "Survey Site")

        # Validate all columns are numeric
        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = pd.to_numeric(df[col], errors="coerce")

        import matplotlib
        matplotlib.use("Agg")   # headless — no display on Railway

        with tempfile.TemporaryDirectory() as tmp_dir:
            agent  = GeoERTAgent()
            result = agent.run(
                df=df, array_type=array_type, terrain=terrain,
                site_name=site_name, save_dir=tmp_dir,
            )

            ert_df         = result["ert_df"]
            inv_result     = result["inv_result"]
            layers         = result["layers"]
            aquifer_result = result["aquifer_result"]
            dz_result      = result["dz_result"]
            curve_info     = result.get("apparent_curve_type", {})

            csv_bytes  = build_annotated_csv(ert_df)
            xlsx_bytes = build_dar_zarouk_excel(
                layers, dz_result, aquifer_result, site_name)
            summary    = build_summary_text(
                site_name, array_type, terrain,
                inv_result, layers, aquifer_result, dz_result, curve_info)

            safe_name = site_name.replace(" ", "_").replace("/", "-")

            # Send plots
            for fname, caption in [
                ("loglog_annotated.png", "📈 *VES Log-Log Curve*"),
                ("dashboard.png",        "📊 *Interpretation Dashboard*"),
                ("borehole_3d.png",      "🕳️ *3D Borehole Model*"),
            ]:
                path = os.path.join(tmp_dir, fname)
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        await update.message.reply_photo(
                            photo=f, caption=caption, parse_mode="Markdown")

            # Send annotated CSV
            await update.message.reply_document(
                document=BytesIO(csv_bytes),
                filename=f"data_with_rho_a_{safe_name}.csv",
                caption=(
                    "📄 *Your data + apparent resistivity*\n"
                    "New columns: `rho_a` (Ohm·m), `K` (geometric factor), `spacing`"
                ),
                parse_mode="Markdown",
            )

            # Send Dar-Zarouk Excel
            await update.message.reply_document(
                document=BytesIO(xlsx_bytes),
                filename=f"dar_zarouk_{safe_name}.xlsx",
                caption=(
                    "📋 *Dar-Zarouk Report (Excel)*\n"
                    "4 sheets: Layer Model · Dar-Zarouk · Aquifer Zones · Summary"
                ),
                parse_mode="Markdown",
            )

            # Send text summary
            await update.message.reply_text(summary, parse_mode="Markdown")

        logger.info("Completed: user=%s site=%s",
                    update.effective_user.id, site_name)

    except KeyError as e:
        await update.message.reply_text(
            f"❌ *Column not found:* `{e}`\n\n"
            f"Check column names match the required format for your array type.",
            parse_mode="Markdown")
    except Exception as e:
        logger.exception("Pipeline error: user=%s", update.effective_user.id)
        await update.message.reply_text(
            f"❌ *Error during processing:*\n`{str(e)}`\n\n"
            "Check your data and send /start to try again.",
            parse_mode="Markdown")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Session cancelled. Send /start to begin.",
        reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *GeoERT Agent — Help*\n\n"
        "/start — begin a new session\n"
        "/cancel — cancel current session\n"
        "/help — show this message\n\n"
        "*Accepted files:* CSV or Excel (.xlsx)\n\n"
        "*Required columns:*\n"
        "• Schlumberger: `AB_2, MN_2, Voltage_mV, Current_mA`\n"
        "• Wenner / DD: `a_spacing, n_factor, Voltage_mV, Current_mA`",
        parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
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
    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))

    logger.info("GeoERT Bot started successfully.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
