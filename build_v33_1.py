"""Build V33.1 — Danger map applies to NEUTRALS only.

V33 gauntlet (20 seeds): wins FFA (place 1.60), loses duels vs V32 (5-7-8).
Root cause: the danger multiplier penalises enemy-owned planets (their
neighborhood is all-enemy → multiplier hits the 0.55 floor), discouraging
exactly the invasion play we need in 2P duels.

Fix: clamp danger multiplier to 1.0 for non-neutral targets. The spatial map
only weighs which neutral to pick. PV bonus still applies everywhere.
"""

with open("d:/Juracan/main_v33.py", encoding="utf-8") as f:
    code = f.read()

code = code.replace(
    "Orbit Wars V33 — PV Scoring + Danger Map.",
    "Orbit Wars V33.1 — PV + Neutral-Only Danger Map."
)
code = code.replace(
    "V33: PV Scoring + Danger Map — V32 spine + present-value target valuation and spatial ally/enemy danger weighting per istinetz writeup",
    "V33.1: PV + Neutral-Only Danger Map — V33 spine, danger multiplier restricted to neutral targets to preserve V32 duel-invasion behavior",
)

OLD = """    def danger_multiplier(self, target):
        \"\"\"Score multiplier in [DANGER_MULT_MIN, DANGER_MULT_MAX] from the
        spatial danger map. 1.0 = neutral, >1 = friendly territory.\"\"\"
        d = self.danger_by_id.get(target.id, 0.5)
        # Map [0,1] -> [min, max] linearly.
        return DANGER_MULT_MIN + d * (DANGER_MULT_MAX - DANGER_MULT_MIN)"""
NEW = """    def danger_multiplier(self, target):
        \"\"\"Score multiplier from the spatial danger map. V33.1: applies only
        to neutral targets — for enemy-owned planets the multiplier is 1.0
        because we WANT to invade enemy territory, especially in duels.\"\"\"
        if target.owner != -1:
            return 1.0
        d = self.danger_by_id.get(target.id, 0.5)
        return DANGER_MULT_MIN + d * (DANGER_MULT_MAX - DANGER_MULT_MIN)"""
assert OLD in code, "danger_multiplier block not found"
code = code.replace(OLD, NEW)

with open("d:/Juracan/main_v33_1.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Built main_v33_1.py")
