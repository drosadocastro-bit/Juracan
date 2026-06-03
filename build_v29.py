"""Build V29 — The All-Seeing Eye."""

with open("d:/Juracan/main_v28.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V28 — Present Value Scoring + Calibrated Fleet Doctrine.",
    "Orbit Wars V29 — The All-Seeing Eye (Fleet Visibility Exploitation)."
)
code = code.replace(
    "V28: Present Value Scoring + Calibrated Fleet Doctrine",
    "V29: The All-Seeing Eye (Fleet Visibility Exploitation)\n"
    "  V28 base + perfect simulation of future planet states based on visible enemy fleet angles.\n"
    "  Implements Vulture Sniping (stealing planets right after enemies capture them)\n"
    "  and prevents suicides into newly arrived enemy fleets."
)

# ── Add TAG_VULTURE and priorities ──
code = code.replace(
    'TAG_EMERGENCY = "EMERGENCY_DEFEND"\nTAG_INTERCEPT = "INTERCEPT"',
    'TAG_EMERGENCY = "EMERGENCY_DEFEND"\nTAG_INTERCEPT = "INTERCEPT"\nTAG_VULTURE = "VULTURE_SNIPE"'
)

code = code.replace(
    """PRI_EMERGENCY = 0
PRI_INTERCEPT = 1
PRI_DUEL_OPEN = 2
PRI_REINFORCE = 3
PRI_SNIPE     = 4
PRI_PRESSURE  = 5
PRI_EXPAND    = 6""",
    """PRI_EMERGENCY = 0
PRI_INTERCEPT = 1
PRI_VULTURE   = 2
PRI_DUEL_OPEN = 3
PRI_REINFORCE = 4
PRI_SNIPE     = 5
PRI_PRESSURE  = 6
PRI_EXPAND    = 7"""
)

# ── Replace _build_fleet_commitments and add simulate_planet_state ──
OLD_COMMITMENTS = """    def _build_fleet_commitments(self):
        w = self.world
        self.arrivals_by_target = defaultdict(set)
        self.arrivals_timeline = defaultdict(lambda: defaultdict(int)) # target_id -> {turn: net_ships}
        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                tid, eta = hit
                if fleet.owner == w.player:
                    self.arrivals_timeline[tid][eta] += fleet.ships
                else:
                    self.arrivals_timeline[tid][eta] -= fleet.ships

        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                target_id, eta = hit
                if fleet.owner != w.player:
                    self.arrivals_by_target[target_id].add(fleet.owner)

        self.friendly_to_enemy = defaultdict(int)
        self.friendly_to_mine = defaultdict(int)
        self.enemy_to_mine = defaultdict(int)
        self.enemy_eta_to_mine = {}

        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit is None:
                continue
            target_id, eta = hit
            target = w.planet_by_id.get(target_id)
            if target is None:
                continue

            if fleet.owner == w.player:
                if target.owner == w.player:
                    self.friendly_to_mine[target_id] += fleet.ships
                else:
                    self.friendly_to_enemy[target_id] += fleet.ships
            elif target.owner == w.player:
                self.enemy_to_mine[target_id] += fleet.ships
                prev = self.enemy_eta_to_mine.get(target_id, eta)
                self.enemy_eta_to_mine[target_id] = min(prev, eta)"""

NEW_COMMITMENTS = """    def _build_fleet_commitments(self):
        w = self.world
        self.arrivals_by_target = defaultdict(set)
        # V29: exact turn-by-turn arrivals
        # target_id -> turn -> owner -> ships
        self.arrivals_timeline = defaultdict(lambda: defaultdict(lambda: defaultdict(int))) 
        
        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                tid, eta = hit
                self.arrivals_timeline[tid][eta][fleet.owner] += fleet.ships
                if fleet.owner != w.player:
                    self.arrivals_by_target[tid].add(fleet.owner)

        self.friendly_to_mine = defaultdict(int)
        self.enemy_to_mine = defaultdict(int)
        self.enemy_eta_to_mine = {}

        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit is None:
                continue
            target_id, eta = hit
            target = w.planet_by_id.get(target_id)
            if target is None:
                continue

            if fleet.owner == w.player:
                if target.owner == w.player:
                    self.friendly_to_mine[target_id] += fleet.ships
            elif target.owner == w.player:
                self.enemy_to_mine[target_id] += fleet.ships
                prev = self.enemy_eta_to_mine.get(target_id, eta)
                self.enemy_eta_to_mine[target_id] = min(prev, eta)
                
    def simulate_planet_state(self, target, up_to_turn):
        w = self.world
        owner = target.owner
        ships = target.ships
        timeline = self.arrivals_timeline.get(target.id, {})
        for t in range(1, int(round(up_to_turn)) + 1):
            if owner != -1:
                ships += target.production
            arrivals = timeline.get(t, {})
            if arrivals:
                player_ships = {}
                for o, s in arrivals.items():
                    player_ships[o] = s
                player_ships[owner] = player_ships.get(owner, 0) + ships
                
                sorted_players = sorted(player_ships.items(), key=lambda item: item[1], reverse=True)
                top_player, top_ships = sorted_players[0]
                
                if len(sorted_players) > 1:
                    second_ships = sorted_players[1][1]
                    survivor_ships = top_ships - second_ships
                    if top_ships == second_ships:
                        survivor_ships = 0
                    survivor_owner = top_player if survivor_ships > 0 else -1
                else:
                    survivor_owner = top_player
                    survivor_ships = top_ships
                
                owner = survivor_owner
                ships = survivor_ships
        return owner, ships"""

code = code.replace(OLD_COMMITMENTS, NEW_COMMITMENTS)

# ── Replace _predict_outcome and capture_need ──
OLD_PREDICT = """    def _predict_outcome(self, target, send_ships, arrival_eta, horizon=25):
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


    def _score_targets(self):"""

NEW_PREDICT = """    def _predict_outcome(self, target, send_ships, arrival_eta, horizon=25):
        w = self.world
        eta = int(round(arrival_eta))
        
        # 1. State at Arrival (simulate up to eta - 1)
        owner, ships = self.simulate_planet_state(target, eta - 1)
        
        # Our landing at eta
        if owner == w.player:
            ships += send_ships
        else:
            ships = send_ships - ships
            if ships <= 0: return -50.0
            owner = w.player

        # 2. Retention Window (simulate from eta to eta + horizon)
        min_ships = ships
        timeline = self.arrivals_timeline.get(target.id, {})
        for t in range(eta, eta + horizon + 1):
            if owner != -1 and t > eta:
                ships += target.production
            
            arrivals = timeline.get(t, {})
            # We already applied our 'send_ships' for turn 'eta'. So don't apply it again,
            # but we DO need to apply any OTHER fleets arriving at turn 'eta'.
            if t == eta:
                arrivals = dict(arrivals) # copy
                arrivals[w.player] = arrivals.get(w.player, 0) + send_ships
                # Also reset ships since we are treating 'ships' as just the garrison *before* combat
                ships = ships - send_ships if owner == w.player else 0
                owner = self.simulate_planet_state(target, eta - 1)[0] # get original owner
                
            if arrivals:
                player_ships = {}
                for o, s in arrivals.items():
                    player_ships[o] = s
                player_ships[owner] = player_ships.get(owner, 0) + ships
                
                sorted_players = sorted(player_ships.items(), key=lambda item: item[1], reverse=True)
                top_player, top_ships = sorted_players[0]
                
                if len(sorted_players) > 1:
                    second_ships = sorted_players[1][1]
                    survivor_ships = top_ships - second_ships
                    if top_ships == second_ships:
                        survivor_ships = 0
                    survivor_owner = top_player if survivor_ships > 0 else -1
                else:
                    survivor_owner = top_player
                    survivor_ships = top_ships
                
                owner = survivor_owner
                ships = survivor_ships
            
            if owner != w.player:
                return -100.0 - (t - eta)
            min_ships = min(min_ships, ships)
            
        return float(min_ships + target.production * horizon)


    def _score_targets(self):"""

code = code.replace(OLD_PREDICT, NEW_PREDICT)

OLD_CAPTURE_NEED = """    def capture_need(self, target, eta):
        \"\"\"How many ships required to actually capture `target` at arrival `eta`.

        Accounts for production growth during transit and for friendly fleets
        already committed. Inflated by any learned capture-buffer multiplier.
        \"\"\"
        w = self.world
        if target.owner == w.player:
            return 0
        if target.owner == -1:
            raw = target.ships + 1
        else:
            growth = int(math.ceil(max(0.0, eta - 1.0) * target.production))
            raw = target.ships + growth + 1
        already_sent = self.friendly_to_enemy.get(target.id, 0)
        remaining = max(0, raw - already_sent)
        return int(math.ceil(remaining * _MEMORY["capture_buffer_mult"]))"""

NEW_CAPTURE_NEED = """    def capture_need(self, target, eta):
        \"\"\"V29: Simulate exact required ships based on true projected state.\"\"\"
        w = self.world
        owner, ships = self.simulate_planet_state(target, eta - 1)
        if owner == w.player:
            return 0
        
        raw = ships + 1
        if owner != -1:
            raw += target.production # production happens before combat on the turn of arrival
            
        return int(math.ceil(raw * _MEMORY["capture_buffer_mult"]))"""

code = code.replace(OLD_CAPTURE_NEED, NEW_CAPTURE_NEED)

# ── Update _score_targets to use simulated state ──
OLD_SCORE_PENALTY = """            # Cost penalty: ships needed to capture
            if t.owner == -1:
                base -= t.ships * 1.5
            else:
                growth = int(min_eta * t.production)
                base -= (t.ships + growth) * 2.0"""

NEW_SCORE_PENALTY = """            owner_at_arrival, projected_ships = self.simulate_planet_state(t, min_eta - 1)
            
            # Cost penalty: ships needed to capture
            if owner_at_arrival == -1:
                base -= projected_ships * 1.5
            else:
                base -= (projected_ships + t.production) * 2.0"""
code = code.replace(OLD_SCORE_PENALTY, NEW_SCORE_PENALTY)

# ── Update classification logic in _best_move_for_source ──
OLD_CLASSIFY = """        # Classify the action.
        if target.owner == world.player:
            continue  # already ours
        if _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT
        elif ctx.duel_opening and target.owner == -1:
            priority = PRI_DUEL_OPEN
            tag = TAG_DUEL_OPEN
        elif target.owner == ctx.leader_owner and ctx.leader_owner != -1:
            priority = PRI_PRESSURE
            tag = TAG_PRESSURE
        elif target.owner == -1:
            # Cheap neutral vs expensive neutral.
            if target.ships <= 8 and _dist(source.x, source.y, target.x, target.y) < 30:
                priority = PRI_EXPAND
                tag = TAG_EXPAND
            else:
                priority = PRI_SNIPE
                tag = TAG_SNIPE
        else:
            priority = PRI_SNIPE
            tag = TAG_SNIPE"""

NEW_CLASSIFY = """        # Classify the action based on true projected state.
        owner_at_arrival, _ = ctx.simulate_planet_state(target, eta - 1)
        if owner_at_arrival == world.player:
            continue  # It will be ours when we arrive! Don't suicide into it.
            
        is_vulture = False
        if target.owner != owner_at_arrival and owner_at_arrival != -1 and owner_at_arrival != world.player:
            is_vulture = True

        if _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT
        elif is_vulture:
            priority = PRI_VULTURE
            tag = TAG_VULTURE
        elif ctx.duel_opening and owner_at_arrival == -1:
            priority = PRI_DUEL_OPEN
            tag = TAG_DUEL_OPEN
        elif owner_at_arrival == ctx.leader_owner and ctx.leader_owner != -1:
            priority = PRI_PRESSURE
            tag = TAG_PRESSURE
        elif owner_at_arrival == -1:
            # Cheap neutral vs expensive neutral.
            if target.ships <= 8 and _dist(source.x, source.y, target.x, target.y) < 30:
                priority = PRI_EXPAND
                tag = TAG_EXPAND
            else:
                priority = PRI_SNIPE
                tag = TAG_SNIPE
        else:
            priority = PRI_SNIPE
            tag = TAG_SNIPE"""

code = code.replace(OLD_CLASSIFY, NEW_CLASSIFY)

with open("d:/Juracan/main_v29.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v29.py")
