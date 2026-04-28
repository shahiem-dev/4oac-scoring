"""4OAC scoring engine.

Resolves a raw species name (as written on a catch sheet) to a canonical
species + computes weight from length using the SASAA formula:

    W_kg = exp(log_a + b * ln(L_cm))

Returns weight=0 for sub-minimum entries, unmatched species in the
zero-score list, and species that cannot be resolved (logged separately).
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPECIES_CSV = DATA_DIR / "species_master.csv"
ALIASES_JSON = DATA_DIR / "species_aliases.json"


@dataclass
class ScoreResult:
    raw_name: str
    canonical_name: str | None
    weight_kg: float
    edible: str  # "Y" / "N" / "?"
    note: str   # "ok" | "zero:sub_minimum" | "zero:unscored_species" | "error:unknown_species"


class Scorer:
    def __init__(self) -> None:
        self.species = pd.read_csv(SPECIES_CSV).set_index("common_name")
        cfg = json.loads(ALIASES_JSON.read_text(encoding="utf-8"))
        self.aliases: dict[str, str] = cfg["aliases"]
        self.zero_score: set[str] = set(cfg["zero_score_species"])

    def _strip_gender(self, name: str) -> tuple[str, str]:
        """Pull a trailing (M)/(F) off the name. Returns (base, gender_or_empty)."""
        m = re.search(r"\s*\((M|F)\)\s*$", name)
        if not m:
            return name.strip(), ""
        return name[: m.start()].strip(), m.group(1)

    def is_site_fish(self, raw_name: str) -> bool:
        return raw_name.strip().lower().startswith("site fish")

    def resolve(self, raw_name: str) -> tuple[str | None, str]:
        """Return (canonical_name_or_None, status)."""
        n = raw_name.strip()
        if "<" in n:
            return None, "zero:sub_minimum"

        # 1. direct alias
        if n in self.aliases:
            return self.aliases[n], "ok"
        # 2. direct match in master
        if n in self.species.index:
            return n, "ok"
        # 3. zero-score base name (with or without gender suffix)
        base, gender = self._strip_gender(n)
        if base in self.zero_score:
            return None, "zero:unscored_species"
        # 4. alias on base + reattach gender
        if base in self.aliases:
            canon = self.aliases[base]
            if gender and f"{canon} ({gender})" in self.species.index:
                return f"{canon} ({gender})", "ok"
            return canon, "ok"
        # 5. base in master
        if base in self.species.index:
            return base, "ok"
        return None, "error:unknown_species"

    def score(self, raw_name: str, length_cm: float | None) -> ScoreResult:
        site = self.is_site_fish(raw_name)
        canon, status = self.resolve(raw_name)
        if canon is None:
            edible = "N" if status == "zero:unscored_species" else "?"
            return ScoreResult(raw_name, None, 0.0, edible, status)
        row = self.species.loc[canon]
        if site:
            return ScoreResult(raw_name, canon, 1.0, row["edible"], "ok:site_fish_flat")
        if length_cm is None or pd.isna(length_cm) or length_cm <= 0:
            return ScoreResult(raw_name, canon, 0.0, row["edible"], "zero:no_length")
        w = math.exp(row["log_a"] + row["b"] * math.log(float(length_cm)))
        return ScoreResult(raw_name, canon, w, row["edible"], "ok")


if __name__ == "__main__":
    s = Scorer()
    tests = [
        ("Galjoen (TL)", 35),
        ("Site Fish (Catfish - White Sea)", 50),
        ("Shark (Smooth Hound - White Spotty) (M)", 90),
        ("Guitarfish (Bluntnose) (F)", 100),
        ("Skate (Biscuit)", 60),
        ("Catshark (Brown)", 40),
        ("Blaasop (Blackback)<0.5kg", 15),
        ("Hottentot", 25),
        ("Gibberish Fish", 30),
    ]
    for name, L in tests:
        r = s.score(name, L)
        print(f"{name:55s} L={L:>4}cm -> canon={r.canonical_name!s:40s} W={r.weight_kg:7.3f}kg ed={r.edible} [{r.note}]")
