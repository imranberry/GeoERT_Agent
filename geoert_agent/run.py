"""
GeoERT Agent — Command-Line Entry Point
========================================
Run the full ERT interpretation pipeline from the terminal.

Usage examples
--------------
# Interpret a Schlumberger survey in sedimentary terrain:
    python run.py --file data/sample_data/schlumberger_sedimentary.csv \
                  --array schlumberger \
                  --terrain sedimentary \
                  --site "Kano Basin VES-01" \
                  --output ./results

# Use synthetic demo data (no CSV needed):
    python run.py --demo --array wenner --terrain basement

# Start the Telegram bot:
    python run.py --bot
"""

import argparse
import os
import sys
import numpy as np

from geoert import GeoERTAgent, SampleDataGenerator


def parse_args():
    parser = argparse.ArgumentParser(
        description="GeoERT Agent — ERT Geophysical Interpretation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="Path to field data CSV file"
    )
    parser.add_argument(
        "--array", "-a",
        choices=["schlumberger", "wenner", "dipole_dipole"],
        default="schlumberger",
        help="Electrode array type (default: schlumberger)"
    )
    parser.add_argument(
        "--terrain", "-t",
        choices=["sedimentary", "basement"],
        default="sedimentary",
        help="Terrain type (default: sedimentary)"
    )
    parser.add_argument(
        "--site", "-s",
        type=str,
        default="Survey Site",
        help="Site/location name for plot titles"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./output",
        help="Output directory for plots and reports (default: ./output)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with synthetic demo data (no CSV required)"
    )
    parser.add_argument(
        "--bot",
        action="store_true",
        help="Start the Telegram bot instead of running the pipeline"
    )
    return parser.parse_args()


def run_pipeline(args):
    """Run the full GeoERT interpretation pipeline."""
    import pandas as pd

    agent = GeoERTAgent()

    if args.demo:
        print(f"\n  Running demo mode ({args.array} · {args.terrain})")
        np.random.seed(42)
        gen = SampleDataGenerator()

        if args.array == "schlumberger":
            df, _ = gen.generate_schlumberger(terrain=args.terrain)
        elif args.array == "wenner":
            df, _ = gen.generate_wenner(terrain=args.terrain)
        else:
            df, _ = gen.generate_dipole_dipole(terrain=args.terrain)

        site = args.site if args.site != "Survey Site" else f"Demo — {args.terrain.title()} · {args.array.title()}"
    else:
        if not args.file:
            print("  ❌ ERROR: Provide --file path or use --demo flag.")
            sys.exit(1)
        if not os.path.exists(args.file):
            print(f"  ❌ ERROR: File not found: {args.file}")
            sys.exit(1)
        df   = pd.read_csv(args.file)
        site = args.site
        print(f"\n  Loaded: {args.file}  ({len(df)} readings)")

    result = agent.run(
        df         = df,
        array_type = args.array,
        terrain    = args.terrain,
        site_name  = site,
        save_dir   = args.output
    )

    import matplotlib.pyplot as plt
    plt.show()

    print(f"\n  ✅ Done. Outputs saved to: {args.output}/")
    return result


def start_bot():
    """Start the Telegram bot."""
    try:
        from bot.telegram_bot import main
        print("  🤖 Starting GeoERT Telegram Bot...")
        main()
    except ImportError:
        print("  ❌ python-telegram-bot not installed.")
        print("     Run: pip install python-telegram-bot")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ Bot error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    args = parse_args()
    if args.bot:
        start_bot()
    else:
        run_pipeline(args)
