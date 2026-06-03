import re

with open("d:/Juracan/main_v19_1.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V19.1 — V7 Spine + Surgical Vulture + Multi-Pass Coordination.",
    "Orbit Wars V20 — Macro-Simulation Engine (Outcome Prediction)."
)
code = code.replace(
    "V19.1: V7 gold spine with refined surgical upgrades:\n"
    "  1. Multi-Pass Coordination (exhaustive 3-pass dedup)\n"
    "  2. Comet Harvesting (grab long-lived low-garrison comets)\n"
    "  3. Tactical Retreat (evacuate hopeless defenses to save ships)\n"
    "  4. Surgical Vulture (bonus to steal planets enemies are fighting over)",
    "V20: Macro-Simulation Engine over V19.1 backbone:\n"
    "  1. Outcome Prediction (25-turn lookahead before launching)\n"
    "  2. Multi-Pass Coordination with Aggregation (Double-Team attacks)\n"
    "  3. Refined Surgical Vulture + Comet Harvesting"
)

code = code.replace(
    '        "target_scores", "arrivals_by_target",',
    '        "target_scores", "arrivals_by_target", "arrivals_timeline",'
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 1: Macro-Simulation (Context methods)
# ═══════════════════════════════════════════════════════════════

SIM_DATA = """        self.arrivals_timeline = defaultdict(lambda: defaultdict(int)) # target_id -> {turn: net_ships}
        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                tid, eta = hit
                if fleet.owner == w.player:
                    self.arrivals_timeline[tid][eta] += fleet.ships
                else:
                    self.arrivals_timeline[tid][eta] -= fleet.ships
"""

code = code.replace(
    '        self.arrivals_by_target = defaultdict(set)',
    '        self.arrivals_by_target = defaultdict(set)\n' + SIM_DATA
)

# Optimized Predict Outcome (no turn-by-turn loop)
PREDICT_OUTCOME = """
    def _predict_outcome(self, target, send_ships, arrival_eta, horizon=25):
        w = self.world
        eta = int(round(arrival_eta))
        timeline = self.arrivals_timeline.get(target.id, {})
        
        # 1. State at Arrival
        ships = target.ships
        if target.owner != -1:
            ships += int(max(0, eta - 1) * target.production)
        
        sorted_events = sorted(timeline.items())
        for t, net in sorted_events:
            if t >= eta: break
            ships += net
            if ships < 0: ships = abs(ships)
        
        # Our landing
        sim_ships = send_ships - ships
        if sim_ships <= 0: return -50.0
        
        # 2. Retention Window
        min_ships = sim_ships
        last_t = eta
        for t, net in sorted_events:
            if t < eta: continue
            if t >= eta + horizon: break
            # Production until this event
            sim_ships += (t - last_t) * target.production
            sim_ships += net
            if sim_ships < 0:
                return -100.0 - (t - eta)
            min_ships = min(min_ships, sim_ships)
            last_t = t
            
        return float(min_ships + target.production * (eta + horizon - last_t))
"""

code = code.replace(
    '    def _score_targets(self):',
    PREDICT_OUTCOME + '\n\n    def _score_targets(self):'
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 2: Scoring Integration (Simulate ONLY if score is competitive)
# ═══════════════════════════════════════════════════════════════

SIM_SCORING = """        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:
            survival = ctx._predict_outcome(target, send, eta)
            if survival < 0:
                score -= 150.0
            else:
                score += min(60.0, survival / 1.5)"""

code = code.replace(
    '        rank = (priority, -score)',
    SIM_SCORING + '\n        rank = (priority, -score)'
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 3: Fleet Aggregation (Double-Team coordination)
# ═══════════════════════════════════════════════════════════════

AGGREGATION_LOGIC = """        for target_id, attackers in target_to_sources.items():
            attackers.sort(key=lambda a: _dist(a[1][2].x, a[1][2].y, a[1][3].x, a[1][3].y))
            target = attackers[0][1][3]
            need = ctx.capture_need(target, attackers[0][1][4])
            total_sent = 0
            for sid, move in attackers:
                final_moves[sid] = move
                sources_to_assign.remove(sid)
                total_sent += move[4]
                if total_sent >= need: break
            excluded_targets.add(target_id)"""

code = code.replace(
    """        for target_id, attackers in target_to_sources.items():
            # Keep the attacker with the lowest ETA (fastest arrival)
            best_attacker = min(attackers, key=lambda a: _dist(
                a[1][2].x, a[1][2].y, a[1][3].x, a[1][3].y))
            
            sid, move = best_attacker
            final_moves[sid] = move
            excluded_targets.add(target_id)
            sources_to_assign.remove(sid)""",
    AGGREGATION_LOGIC
)

with open("d:/Juracan/main_v20.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v20.py")
