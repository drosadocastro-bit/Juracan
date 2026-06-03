"""Build V28 — Present Value Scoring.

V27.1 base + replace flat production scoring with time-discounted
Present Value. A planet's value depends on when we can capture it:
   PV = production * (gamma^eta - gamma^horizon) / (1 - gamma)
A nearby prod-5 planet is worth much more than a distant prod-5 planet
because we start earning sooner.
"""

with open("d:/Juracan/main_v27_1.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V27.1 — Calibrated Fleet Doctrine.",
    "Orbit Wars V28 — Present Value Scoring + Calibrated Fleet Doctrine."
)
code = code.replace(
    "V27.1: Calibrated Fleet Doctrine\n"
    "  V20 core with calibrated concentration minimums.\n"
    "  Early game: V20 tempo (grab neutrals fast with small fleets).\n"
    "  Mid/Late game: bigger fleets to exploit speed scaling.",
    "V28: Present Value Scoring + Calibrated Fleet Doctrine\n"
    "  V27.1 base (calibrated concentration minimums).\n"
    "  Replaces flat production scoring with time-discounted Present Value.\n"
    "  PV = prod * (gamma^eta - gamma^horizon) / (1-gamma).\n"
    "  Nearby high-prod planets are worth much more than distant ones."
)

# ── Replace _score_targets with Present Value version ──
OLD_SCORE = """    def _score_targets(self):
        \"\"\"Pre-score every non-owned planet as an attack candidate.\"\"\"
        w = self.world
        self.target_scores = {}
        for t in w.planets:
            if t.owner == w.player:
                continue
            if t.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][t.id] > _MEMORY["turn"]:
                continue
            # Static value of capturing this planet.
            base = t.production * (92.0 if t.owner == -1 else 118.0)
            if self.duel_opening and t.owner == -1:
                base += t.production * 70.0
                base += max(0.0, 18.0 - t.ships) * 2.2
            if self.ffa_opening and t.owner == -1:
                base += t.production * 26.0
                base += max(0.0, 18.0 - t.ships) * 0.9
                if t.production >= 3 and t.ships <= 16:
                    base += 24.0
            if self.ffa_behind and t.owner == self.leader_owner:
                base += 110.0
            if t.owner == self.leader_owner:
                base += 72.0
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)
            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over.
            enemy_attackers = self.arrivals_by_target.get(t.id, set())
            is_conflict = len(enemy_attackers) >= 2
            if t.owner != -1:
                # If owner is in a fight with at least one attacker
                for attacker_owner in enemy_attackers:
                    if attacker_owner != t.owner:
                        is_conflict = True
                        break
            
            if is_conflict:
                base += 45.0
            
            # V19.1 UPGRADE 2: Comet Harvesting — grab long-lived low-garrison comets.
            if t.id in w.comet_paths:
                remaining = _comet_remaining_turns(t, w.comet_paths)
                if remaining < 15:
                    base -= 120.0  # Too short-lived
                elif remaining < 28:
                    if t.production >= 2 and t.ships <= 6:
                        base += 15.0  # Quick grab opportunity
                    else:
                        base -= 50.0
                else:
                    if t.production >= 3 and t.ships <= 8:
                        base += 10.0
                    else:
                        base -= 10.0
            self.target_scores[t.id] = base"""

NEW_SCORE = """    def _score_targets(self):
        \"\"\"V28: Present Value scoring — time-discounted production value.
        
        PV = prod * (gamma^eta - gamma^horizon) / (1 - gamma)
        This makes nearby high-production planets dramatically more valuable
        than distant ones, because we start earning from them sooner.
        \"\"\"
        w = self.world
        self.target_scores = {}
        gamma = 0.985  # Discount factor per turn
        horizon = max(50, 500 - w.step)  # Remaining useful turns
        
        for t in w.planets:
            if t.owner == w.player:
                continue
            if t.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][t.id] > _MEMORY["turn"]:
                continue
            
            # Estimate rough ETA from our nearest planet
            min_eta = 999.0
            for mp in w.my_planets:
                d = _dist(mp.x, mp.y, t.x, t.y)
                # Estimate with medium fleet speed (~3.0)
                eta_est = d / 3.0
                if eta_est < min_eta:
                    min_eta = eta_est
            min_eta = max(1.0, min_eta)
            
            # Present Value of future production
            pv = t.production * (gamma ** min_eta - gamma ** horizon) / (1.0 - gamma)
            
            # Base score from PV
            base = pv
            
            # Cost penalty: ships needed to capture
            if t.owner == -1:
                base -= t.ships * 1.5
            else:
                growth = int(min_eta * t.production)
                base -= (t.ships + growth) * 2.0
            
            # Context bonuses (preserved from V20)
            if self.duel_opening and t.owner == -1:
                base += t.production * 70.0
                base += max(0.0, 18.0 - t.ships) * 2.2
            if self.ffa_opening and t.owner == -1:
                base += t.production * 26.0
                base += max(0.0, 18.0 - t.ships) * 0.9
                if t.production >= 3 and t.ships <= 16:
                    base += 24.0
            if self.ffa_behind and t.owner == self.leader_owner:
                base += 110.0
            if t.owner == self.leader_owner:
                base += 72.0
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)
            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # Surgical Vulture — steal planets enemies are fighting over.
            enemy_attackers = self.arrivals_by_target.get(t.id, set())
            is_conflict = len(enemy_attackers) >= 2
            if t.owner != -1:
                for attacker_owner in enemy_attackers:
                    if attacker_owner != t.owner:
                        is_conflict = True
                        break
            
            if is_conflict:
                base += 45.0
            
            # Comet Harvesting.
            if t.id in w.comet_paths:
                remaining = _comet_remaining_turns(t, w.comet_paths)
                if remaining < 15:
                    base -= 120.0
                elif remaining < 28:
                    if t.production >= 2 and t.ships <= 6:
                        base += 15.0
                    else:
                        base -= 50.0
                else:
                    if t.production >= 3 and t.ships <= 8:
                        base += 10.0
                    else:
                        base -= 10.0
            self.target_scores[t.id] = base"""

code = code.replace(OLD_SCORE, NEW_SCORE)

with open("d:/Juracan/main_v28.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v28.py")
