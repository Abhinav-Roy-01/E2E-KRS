"""Deliberate name-inconsistency generator.

Simulates how the same real-world institute gets spelled differently across
systems built by different vendors/teams (no shared master ID anywhere).

Every source (MySQL, Postgres, Mongo, legacy CSV) reads the canonical names
from institute_registry.json and pushes them through this module before
inserting, so the *same* institute appears differently in each database.
"""
from __future__ import annotations

import random
from typing import Callable

# ---------------------------------------------------------------------------
# Individual noise transforms
# ---------------------------------------------------------------------------

HONORIFICS = ["Shri ", "Sri ", "Smt. ", "Dr. ", "St. ", "The ", "Sree ", "Seth "]


def drop_honorific(name: str) -> str:
    for h in HONORIFICS:
        if name.startswith(h):
            return name[len(h):]
    return name


def amp_and(name: str) -> str:
    if "&" in name:
        return name.replace("&", "and")
    return name.replace(" and ", " & ")


def abbreviate(name: str) -> str:
    return (
        name.replace("Institute of Technology", "Inst. of Tech.")
        .replace("Institute of Engineering and Technology", "Inst. of Engg. & Tech.")
        .replace("College of Engineering and Technology", "Colg. of Engg. & Tech.")
        .replace("College of Engineering", "Colg. of Engg.")
        .replace("Engineering College", "Engg. College")
        .replace("Institute", "Inst.")
        .replace("Engineering", "Engg.")
        .replace("Polytechnic", "Poly.")
    )


def all_caps(name: str) -> str:
    return name.upper()


def title_case(name: str) -> str:
    return name.title()


def double_space(name: str) -> str:
    return name.replace(" ", "  ", 1)


def trailing_punct(name: str) -> str:
    return name.rstrip() + "."


def strip_city(name: str) -> str:
    """Drop the ', District' tail so the name is location-free."""
    if ", " in name:
        return name.split(", ")[0]
    return name


def reorder_city(name: str) -> str:
    """'X College of Engineering, Y' -> 'Y X College of Engineering'."""
    if ", " in name:
        core, city = name.rsplit(", ", 1)
        return f"{city} {core}"
    return name


def swap_suffix_order(name: str) -> str:
    """'College of Engineering' <-> 'Engineering College'."""
    if "College of Engineering" in name:
        return name.replace("College of Engineering", "Engineering College")
    if "Engineering College" in name:
        return name.replace("Engineering College", "College of Engineering")
    return name


TRANSFORMS: list[Callable[[str], str]] = [
    drop_honorific,
    amp_and,
    abbreviate,
    all_caps,
    title_case,
    double_space,
    trailing_punct,
    strip_city,
    reorder_city,
    swap_suffix_order,
]


def noisy_variant(
    name: str,
    rng: random.Random | None = None,
    min_transforms: int = 1,
    max_transforms: int = 2,
) -> str:
    """Produce 1 noisy variant of a canonical institute name."""
    rng = rng or random
    out = name
    n = rng.randint(min_transforms, max_transforms)
    for _ in range(n):
        out = rng.choice(TRANSFORMS)(out)
    return out


def legacy_messy_variant(name: str, rng: random.Random) -> str:
    """Messier variant for the oldest, least-maintained source (CSV files)."""
    out = noisy_variant(name, rng, min_transforms=2, max_transforms=3)
    if rng.random() < 0.25:
        out = "  " + out + " "  # stray leading/trailing whitespace
    elif rng.random() < 0.15:
        out = out + " ,"  # stray comma
    return out


def noisy_bool(rng: random.Random, probability: float) -> bool:
    return rng.random() < probability
