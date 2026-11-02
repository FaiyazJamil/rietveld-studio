"""Small strict chemical-formula parser used for COD search and ranking only."""
from __future__ import annotations

import re
from collections import defaultdict

ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split())
ALIASES = {"LFP": "LiFePO4", "LMFP": "LiMn0.6Fe0.4PO4", "LTO": "Li4Ti5O12",
           "NMC622": "LiNi0.6Mn0.2Co0.2O2", "NMC811": "LiNi0.8Mn0.1Co0.1O2",
           "LCO": "LiCoO2", "LNO": "LiNiO2"}
SUBSCRIPT = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def parse_formula(formula: str) -> dict[str, float]:
    formula = ALIASES.get(formula.strip().upper(), formula.strip()).translate(SUBSCRIPT)
    formula = re.sub(r"\s+", "", formula)
    if not formula or len(formula) > 200:
        raise ValueError("Enter a formula such as LiFePO4, LiMn0.6Fe0.4PO4, or a supported alias (LFP/LMFP).")
    # Middle-dot hydrates are unambiguous; ASCII decimal points are not separators.
    pieces = re.split(r"[·•]", formula)
    total = defaultdict(float)
    for part in pieces:
        multiplier = 1.0
        match = re.match(r"^(\d+(?:\.\d+)?)(?=[A-Z(\[])", part)
        if match:
            multiplier, part = float(match[1]), part[match.end():]
        tokens = re.findall(r"[A-Z][a-z]?|\d+(?:\.\d+)?|\.\d+|[()\[\]]", part)
        if "".join(tokens) != part:
            raise ValueError("Formula contains unsupported syntax. For names (e.g. olivine), use keyword search.")
        stack = [defaultdict(float)]
        brackets = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in {"(", "["}:
                stack.append(defaultdict(float))
                brackets.append(token)
            elif token in {")", "]"}:
                if len(stack) < 2 or brackets.pop() != {")": "(", "]": "["}[token]:
                    raise ValueError("Unbalanced formula parentheses.")
                group = stack.pop()
                factor = 1.0
                if i + 1 < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", tokens[i + 1]):
                    i += 1
                    factor = float(tokens[i])
                for element, amount in group.items():
                    stack[-1][element] += amount * factor
            elif token in ELEMENTS:
                factor = 1.0
                if i + 1 < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", tokens[i + 1]):
                    i += 1
                    factor = float(tokens[i])
                stack[-1][token] += factor
            else:
                raise ValueError(f"Unknown element or misplaced number: {token}")
            i += 1
        if len(stack) != 1:
            raise ValueError("Unbalanced formula parentheses.")
        for element, amount in stack[0].items():
            total[element] += amount * multiplier
    if not total or any(v <= 0 for v in total.values()):
        raise ValueError("All element amounts must be positive.")
    return dict(total)


def hill_formula(composition: dict[str, float]) -> str:
    order = sorted(composition)
    if "C" in composition:
        order = ["C"] + (["H"] if "H" in composition else []) + [e for e in order if e not in {"C", "H"}]
    return " ".join(e + (f"{composition[e]:g}" if abs(composition[e] - 1) > 1e-8 else "") for e in order)


def composition_distance(target: dict, candidate: dict) -> float:
    elements = set(target) | set(candidate)
    a, b = sum(target.values()), sum(candidate.values())
    return sum(abs(target.get(e, 0) / a - candidate.get(e, 0) / b) for e in elements)

