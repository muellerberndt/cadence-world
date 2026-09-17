"""Summarise a sweep of probe runs: python sim/summarize.py <dir with *.jsonl>

One row per run: the population at the end, the mean genome, the lifetime-at-death medians by
brain size and by cortex count, the symbol statistics against their chance level, and the reward
per tick of creatures that hear against those that do not.
"""

import json
import sys
from pathlib import Path


def load(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
    final = next((r for r in rows if r.get("final")), None)
    last = next((r for r in reversed(rows) if not r.get("final")), None)
    return last, final


def main(folder):
    files = sorted(Path(folder).glob("*.jsonl"))
    print(f"{'run':28} {'alive':>5} {'age':>4} {'cells':>5} {'ctx':>4} {'hor':>4} {'rad':>4} {'spk':>4} {'inr':>4} {'hlv':>4} | life by cells (median) | life by cortices | life plain/recurrent/halves | MI food/nb/kin vs chance | reward hears/deaf")
    for f in files:
        last, final = load(f)
        if not last:
            print(f"{f.stem:28} (no output)")
            continue
        life = final["lifeByCells"] if final else {}
        by_cells = " ".join(f"{k}:{v['median']}" for k, v in sorted(life.items(), key=lambda kv: int(kv[0])) if v["n"] >= 30)
        byc = final["lifeByCortices"] if final else {}
        by_ctx = " ".join(f"{k}:{v['median']}({v['n']})" for k, v in sorted(byc.items()))
        byh = final.get("lifeByHalves", {}) if final else {}
        by_halves = " ".join(f"{k[:3]}:{v['median']}({v['n']})" for k, v in byh.items())
        sym = final["symbols"] if final else {}
        mi = " ".join(f"{sym[k]['mi']:.3f}/{sym[k]['chance']:.3f}" for k in ("food", "neighbour", "kin")) if sym else ""
        rw = final["rewardPerTick"] if final else {}
        print(f"{f.stem:28} {last['alive']:>5} {last['age']:>4} {last['cells']:>5} {last['cortices']:>4} {last['horizon']:>4} {last['radius']:>4} {last['speak']:>4} {last.get('inner', 0):>4} {last.get('halves', 0):>4} | {by_cells:22} | {by_ctx:16} | {by_halves:22} | {mi:26} | {rw.get('hears')}/{rw.get('deaf')}"
              + ("" if final else "  (running)"))
    print()
    for f in files:
        last, final = load(f)
        if last and final:
            print(f"{f.stem:28} census {last['census']}  horizons {last['horizonHist']}  cortices {last['corticesHist']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "receipts")
