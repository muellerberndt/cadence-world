"""Variant sweep for the survival lane: one process per configuration.

Axes: observation wiring against its matched controls, the parameter prior
(the Doom lane's decisive constant), and the temporal-context window. Each
job runs the complete bounded pipeline and writes its own receipt; a summary
row per job lands in `results.jsonl`. Checkpoints and trace frames are kept
only in full receipts, not in sweep receipts, to bound artifact size.

Brains are independent, so jobs parallelize across processes; each brain's
own experience stays ordered inside its job.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import time
from pathlib import Path

from .survival import run

AXES = {
    "architecture": ("recursive", "composed", "flat"),
    "parameter_prior": (0.1, 0.4, 1.0),
    "seed": (0, 1),
}
HISTORY_PROBE = (1, 4)  # recursive only: does removing temporal context cost?


def jobs():
    rows = []
    for architecture in AXES["architecture"]:
        for prior in AXES["parameter_prior"]:
            for seed in AXES["seed"]:
                rows.append(
                    {
                        "architecture": architecture,
                        "parameter_prior": prior,
                        "seed": seed,
                        "history_steps": 4,
                    }
                )
    for steps in HISTORY_PROBE:
        if steps != 4:
            for seed in AXES["seed"]:
                rows.append(
                    {
                        "architecture": "recursive",
                        "parameter_prior": 0.4,
                        "seed": seed,
                        "history_steps": steps,
                    }
                )
    return rows


def name(job):
    return (
        f"{job['architecture']}-p{job['parameter_prior']}"
        f"-h{job['history_steps']}-s{job['seed']}"
    )


def execute(task):
    job, out_dir, options = task
    started = time.perf_counter()
    try:
        receipt = run(**job, **options)
    except Exception as error:  # a refused variant is a result, not a crash
        return {"name": name(job), **job, "failed": repr(error)}
    receipt.pop("checkpoints", None)
    receipt["norms"] = None
    for phase in ("before_learning", "after_learning"):
        receipt[phase]["frames"] = []
        receipt[phase]["dens"] = None
    for control in receipt["controls"].values():
        control["frames"] = []
        control["dens"] = None
    path = Path(out_dir) / f"{name(job)}.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    probes = receipt["after_learning"]["probes"]
    return {
        "name": name(job),
        **job,
        "alignment": [a["agreement"] for a in receipt["alignment"]],
        "bootstrap_reasons": [r["reason"] for r in receipt["bootstrap"]],
        "before_survival": receipt["before_learning"]["mean_survival_ticks"],
        "after_survival": receipt["after_learning"]["mean_survival_ticks"],
        "after_food": receipt["after_learning"]["mean_food_eaten"],
        "teacher_survival": receipt["controls"]["teacher"]["mean_survival_ticks"],
        "reflex_survival": receipt["controls"]["reflex"]["mean_survival_ticks"],
        "random_survival": receipt["controls"]["random"]["mean_survival_ticks"],
        "untrained_survival": receipt["controls"]["untrained"]["mean_survival_ticks"],
        "threat_response": [p["threat_response"] for p in probes],
        "den_rate_under_threat": [p["den_rate_under_threat"] for p in probes],
        "seconds": time.perf_counter() - started,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("runs/sweep"))
    parser.add_argument("--processes", type=int, default=None)
    parser.add_argument("--beings", type=int, default=2)
    parser.add_argument("--learn-episodes", type=int, default=8)
    parser.add_argument("--eval-episodes", type=int, default=3)
    parser.add_argument("--ticks", type=int, default=240)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    options = {
        "beings": args.beings,
        "learn_episodes": args.learn_episodes,
        "eval_episodes": args.eval_episodes,
        "ticks": args.ticks,
    }
    tasks = [(job, str(args.out), options) for job in jobs()]
    results_path = args.out / "results.jsonl"
    with multiprocessing.Pool(processes=args.processes) as pool:
        with results_path.open("a") as sink:
            for row in pool.imap_unordered(execute, tasks):
                sink.write(json.dumps(row) + "\n")
                sink.flush()
                print(row.get("name"), row.get("failed", ""), flush=True)


if __name__ == "__main__":
    main()
