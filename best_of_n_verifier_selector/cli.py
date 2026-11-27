"""CLI for Best-of-N Verifier Selector."""
import argparse
import json
from .core import CandidatePatch, select_best_patch


def main() -> None:
    parser = argparse.ArgumentParser(description="Select cleanest passing patch from N candidates")
    parser.add_argument("--input", required=True, help="JSON file of candidate patch records")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    cands = [CandidatePatch(**item) for item in raw]
    res = select_best_patch(cands)
    if res.winner:
        print(f"WINNER: {res.winner.candidate_id}")
    else:
        print("NO ELIGIBLE PATCH")


if __name__ == "__main__":
    main()
