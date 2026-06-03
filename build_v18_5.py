import re

with open("d:/Juracan/main_v7.py", encoding="utf-8") as f:
    code = f.read()

# Replace docstring
code = code.replace(
    "Orbit Wars V4 — OODA-L agent.",
    "Orbit Wars V18.5 — Timeline Sniper Engine (Bugfix)."
).replace(
    "Patched locally as V7: V5 core restored, with a restrained 4-player tempo\nadjustment that boosts early neutral growth without outranking leader pressure.",
    "V18.5: Pure V7 baseline with Timeline Sniper Engine. Fixed friendly-fire bug by ignoring planets we are already targeting."
)

TIMELINE_SIMULATOR = """
    def _simulate_timelines(self):
        w = self.world
        arrivals = defaultdict(list)
        my_targets = set()
        
        for fleet in w.fleets:
            forecast = w.fleet_forecasts.get(fleet.id)
            if forecast:
                target_id, hit_turn = forecast
                arrivals[target_id].append((hit_turn, fleet.owner, fleet.ships))
                if fleet.owner == w.player:
                    my_targets.add(target_id)
                
        self.snipe_opportunities = []
        
        for p in w.planets:
            # Skip if we already own it, or if our main army is already targeting it!
            if p.owner == w.player or p.id in my_targets:
                continue
                
            arrs = arrivals.get(p.id)
            if not arrs:
                continue
                
            arrs.sort(key=lambda x: x[0])
            current_owner = p.owner
            current_ships = p.ships
            
            max_eta = arrs[-1][0]
            vulnerable_turn = None
            
            for turn in range(1, max_eta + 2):
                if current_owner != -1:
                    current_ships += p.production
                
                turn_arrs = [a for a in arrs if a[0] == turn]
                if turn_arrs:
                    forces = defaultdict(int)
                    for _, owner, ships in turn_arrs:
                        forces[owner] += ships
                    forces[current_owner] += current_ships
                    
                    sorted_forces = sorted(forces.items(), key=lambda x: x[1], reverse=True)
                    if len(sorted_forces) == 1:
                        current_owner = sorted_forces[0][0]
                        current_ships = sorted_forces[0][1]
                    else:
                        first = sorted_forces[0]
                        second = sorted_forces[1]
                        if first[1] > second[1]:
                            current_owner = first[0]
                            current_ships = first[1] - second[1]
                        else:
                            current_owner = -1
                            current_ships = 0
                            
                # If it's weak and owned by an enemy, snipe it
                if current_owner not in (-1, w.player) and current_ships <= 5:
                    if vulnerable_turn is None:
                        vulnerable_turn = turn + 1
                        self.snipe_opportunities.append((p.id, vulnerable_turn, current_owner, current_ships))
                        break # Only snipe it once!
"""

# Inject into Context
ctx_init = """    def __init__(self, world):
        self.world = world
        self._build_fleet_commitments()
        self._build_power_table()
        self._build_reserves_and_surplus()
        self._score_targets()"""

ctx_init_new = """    def __init__(self, world):
        self.world = world
        self._build_fleet_commitments()
        self._build_power_table()
        self._build_reserves_and_surplus()
        self._score_targets()
        self._simulate_timelines()"""

code = code.replace(ctx_init, ctx_init_new)
code = code.replace("    def _build_fleet_commitments(self):", TIMELINE_SIMULATOR + "\n    def _build_fleet_commitments(self):")


SNIPE_LOGIC = """
    # ------- Priority 2.5: TIMELINE_SNIPE -------
    PRI_TIMELINE_SNIPE = 2.5
    for target_id, snipe_turn, expected_owner, remaining_ships in ctx.snipe_opportunities:
        target = world.planet_by_id.get(target_id)
        if target is None or target.owner == world.player:
            continue
            
        for source in world.my_planets:
            avail = ctx.surplus_by_id.get(source.id, 0) - used_surplus[source.id]
            if avail < _min_launch_size(world.step):
                continue
                
            send = max(int(remaining_ships) + 3, _min_launch_size(world.step))
            if send > avail:
                continue
                
            aim = _aim_solution(source, target, send, world.angular_velocity, world.comet_paths, world.planets, _MEMORY["path_tolerance"])
            if aim is None:
                continue
                
            angle, eta, _, _ = aim
            
            # The snipe is only valid if we arrive exactly when it's vulnerable (±1.5 turns)
            if abs(eta - snipe_turn) <= 1.5:
                decisions.append((PRI_TIMELINE_SNIPE, "TIMELINE_SNIPE", source, target, int(send), angle))
                used_surplus[source.id] += send
                break
"""

# Inject into decide() right before Priority 1-5 loop
pri_1_5_marker = "    # ------- Priority 1-5: one action per source -------"
code = code.replace(pri_1_5_marker, SNIPE_LOGIC + "\n" + pri_1_5_marker)


with open("d:/Juracan/main_v18_5.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v18_5.py")
