import csv
import re
import subprocess
from datetime import datetime
from pathlib import Path


def status(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


fixtures = list(csv.DictReader(Path("data/world_cup_2026/fixtures.csv").open()))
as_of = max(row["date"] for row in fixtures if row["home_score"] and row["away_score"])

status(f"Updating forecast.as_of to {as_of}")
config_path = Path("config/model.yaml")
config = config_path.read_text()
config_path.write_text(
    re.sub(r'  as_of: "\d{4}-\d{2}-\d{2}"', f'  as_of: "{as_of}"', config, count=1)
)

run_dir = Path("outputs") / as_of
status("Starting prediction")
subprocess.run(["wc-forecaster", "predict"], check=True)
status("Completed prediction")
status("Starting bracket rendering")
subprocess.run(["python3", "scripts/draw_knockout_bracket.py", "--run-dir", str(run_dir)], check=True)
status("Completed bracket rendering")
status("Starting round probability plotting")
subprocess.run(["Rscript", "scripts/plot_round_reach_probabilities.R", "--run-dir", str(run_dir)], check=True)
status("Completed round probability plotting")
