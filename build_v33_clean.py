"""build_v33_clean.py — Anti-Vulture Defense from V27.1 backbone.

Hypothesis (the ONE structural change in this version):
  V27.1's launch decision uses _predict_outcome(target, send, eta) to check
  whether the TARGET survives our capture. It does NOT check whether the
  SOURCE survives losing `send` ships to inbound enemy fleets.
  Strong ladder agents are vultures: they queue strikes that arrive at our
  source right after we launch, capturing depleted planets. Adding a
  symmetric _predict_source_survival check should plug that hole.

Scope: single targeted change, no other tuning.
  Patch 1: add Context._predict_source_survival method (after _predict_outcome).
  Patch 2: invoke it in _best_move_for_source scoring, penalize unsafe launches.

Validation gate: gauntlet3 vs V27.1 must show CI lower bound >= -0.1 and
mean >= +0.3 before we submit. Anything weaker = HOLD / iterate.
"""
SRC = "main_v27_1.py"
DST = "main_v33_clean.py"

with open(SRC, "r", encoding="utf-8") as f:
    code = f.read()

# ----- Patch 1: insert source-survival method right after _predict_outcome -----
OLD_1 = '''            min_ships = min(min_ships, sim_ships)
            last_t = t
            
        return float(min_ships + target.production * (eta + horizon - last_t))


    def _score_targets(self):'''

NEW_1 = '''            min_ships = min(min_ships, sim_ships)
            last_t = t
            
        return float(min_ships + target.production * (eta + horizon - last_t))


    def _predict_source_survival(self, source, send_ships, horizon=20):
        """V33-clean: anti-vulture defense.

        Simulate the SOURCE planet's garrison over `horizon` turns assuming
        we launch `send_ships` right now. Returns the minimum projected
        garrison (negative => source falls => bad launch).

        Symmetric to _predict_outcome: reuses arrivals_timeline (net_ships
        per turn, friendly positive / enemy negative), adds our production
        each turn, and tracks the dip.

        Hypothesis: V27.1 over-launches when a vulture is en route, leaving
        the source killable. A negative survival score should veto the launch.
        """
        ships = source.ships - send_ships
        if ships < 0:
            return -200.0  # would over-launch, shouldn't happen but defensive
        timeline = self.arrivals_timeline.get(source.id, {})
        sorted_events = sorted(timeline.items())
        min_ships = ships
        last_t = 0
        for t, net in sorted_events:
            if t > horizon:
                break
            # Produce continuously until this event lands.
            ships += (t - last_t) * source.production
            ships += net
            if ships < 0:
                # Source falls at turn t. Deeper = worse, earlier = worse.
                return -100.0 - (horizon - t)
            min_ships = min(min_ships, ships)
            last_t = t
        # No-event tail: just accrues production. Don't reward it heavily.
        return float(min_ships)


    def _score_targets(self):'''

assert OLD_1 in code, "Patch 1 anchor not found"
code = code.replace(OLD_1, NEW_1, 1)

# ----- Patch 2: invoke source survival in _best_move_for_source -----
OLD_2 = '''        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:
            survival = ctx._predict_outcome(target, send, eta)
            if survival < 0:
                score -= 150.0
            else:
                score += min(60.0, survival / 1.5)
        rank = (priority, -score)'''

NEW_2 = '''        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:
            survival = ctx._predict_outcome(target, send, eta)
            if survival < 0:
                score -= 150.0
            else:
                score += min(60.0, survival / 1.5)
            # V33-clean: anti-vulture defense. Penalise launches that doom
            # the source planet. EMERGENCY launches bypass this — when our
            # planet is already under attack we may need to launch anyway.
            if priority != PRI_EMERGENCY:
                src_survival = ctx._predict_source_survival(source, send)
                if src_survival < 0:
                    score -= 180.0  # heavier than target penalty: losing
                                    # an OWNED planet is strictly worse than
                                    # failing to capture a new one.
                elif src_survival < 3:
                    score -= 40.0   # uncomfortable but survivable
        rank = (priority, -score)'''

assert OLD_2 in code, "Patch 2 anchor not found"
code = code.replace(OLD_2, NEW_2, 1)

with open(DST, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Wrote {DST} ({len(code):,} bytes)")
print("Changes: 2 patches (source-survival method + scoring call).")
