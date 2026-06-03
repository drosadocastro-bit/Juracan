"""
Extract per-turn board features and outcome labels from Orbit Wars replay JSONs.

Outputs features.npz with:
  X: (N, 15) float32 feature matrix
  y_win: (N,) float32 final game outcome (1=win, 0=loss)
  y_delta: (N,) float32 ship-count delta after 15 turns (normalized)
  game_ids: (N,) int32 game index per row
  player_ids: (N,) int32 player slot per row
  turns: (N,) int32 step number per row
  action_stats: (N, 4) float32 [n_launches, total_ships, avg_fleet_size, multi_launch]
"""

import glob
import json
import math
import os
import sys
import numpy as np


REPLAYS_DIR = os.path.join(os.path.dirname(__file__), "replays")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "features.npz")

CENTER_X, CENTER_Y = 50.0, 50.0
BOARD_SIZE = 100.0


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def extract_features_from_replay(filepath):
    """Extract per-turn features for every player in a replay."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    steps = data.get("steps", [])
    if len(steps) < 5:
        return []

    n_agents = len(steps[0])
    n_steps = len(steps)

    # Determine final rewards
    final_rewards = []
    for i in range(n_agents):
        r = steps[-1][i].get("reward", 0)
        final_rewards.append(1.0 if r == 1 else 0.0)

    rows = []

    for step_idx in range(1, n_steps):
        step = steps[step_idx]

        # Get the shared observation from agent 0 (planets/fleets are global)
        obs = step[0].get("observation", {})
        if not obs:
            continue

        planets = obs.get("planets", [])
        fleets = obs.get("fleets", [])
        game_step = obs.get("step", step_idx)

        if not planets:
            continue

        for agent_idx in range(n_agents):
            agent_obs = step[agent_idx].get("observation", {})
            player_id = agent_obs.get("player", agent_idx) if agent_obs else agent_idx

            # --- Board features for this player ---
            my_ships = 0
            my_production = 0
            my_planets_count = 0
            enemy_ships = 0
            enemy_production = 0
            enemy_planets_count = 0
            neutral_ships = 0
            neutral_planets_count = 0
            nearest_enemy_dist = 999.0
            total_production = 0

            my_planet_positions = []
            enemy_planet_positions = []

            for p in planets:
                pid, owner, px, py, radius, ships, prod = (
                    int(p[0]), int(p[1]), float(p[2]), float(p[3]),
                    float(p[4]), int(p[5]), int(p[6])
                )
                total_production += prod
                if owner == player_id:
                    my_ships += ships
                    my_production += prod
                    my_planets_count += 1
                    my_planet_positions.append((px, py))
                elif owner == -1:
                    neutral_ships += ships
                    neutral_planets_count += 1
                else:
                    enemy_ships += ships
                    enemy_production += prod
                    enemy_planets_count += 1
                    enemy_planet_positions.append((px, py))

            # Nearest enemy distance (planet centroid to planet centroid)
            if my_planet_positions and enemy_planet_positions:
                for mx, my_ in my_planet_positions:
                    for ex, ey in enemy_planet_positions:
                        d = dist(mx, my_, ex, ey)
                        if d < nearest_enemy_dist:
                            nearest_enemy_dist = d

            # Fleet counts
            my_fleet_ships = 0
            enemy_fleet_ships = 0
            my_fleet_count = 0
            enemy_fleet_count = 0
            for fl in fleets:
                f_owner = int(fl[1])
                f_ships = int(fl[6])
                if f_owner == player_id:
                    my_fleet_ships += f_ships
                    my_fleet_count += 1
                elif f_owner >= 0:
                    enemy_fleet_ships += f_ships
                    enemy_fleet_count += 1

            # Derived features
            total_my = my_ships + my_fleet_ships
            total_enemy = enemy_ships + enemy_fleet_ships
            prod_ratio = my_production / max(1, total_production)
            ship_ratio = total_my / max(1, total_my + total_enemy)
            territory_pct = my_planets_count / max(1, my_planets_count + enemy_planets_count + neutral_planets_count)
            game_progress = game_step / 500.0

            features = np.array([
                total_my,                  # 0: our total ships
                my_production,             # 1: our production
                my_planets_count,          # 2: our planet count
                total_enemy,               # 3: enemy total ships
                enemy_production,          # 4: enemy production
                enemy_planets_count,       # 5: enemy planet count
                neutral_ships,             # 6: neutral ships remaining
                neutral_planets_count,     # 7: neutral planets remaining
                nearest_enemy_dist,        # 8: nearest enemy distance
                my_fleet_count,            # 9: our fleets in transit
                enemy_fleet_count,         # 10: enemy fleets in transit
                prod_ratio,                # 11: our share of total production
                ship_ratio,                # 12: our share of total ships
                territory_pct,             # 13: our share of all planets
                game_progress,             # 14: game progress [0,1]
            ], dtype=np.float32)

            # --- Action features ---
            actions = step[agent_idx].get("action", []) or []
            n_launches = len(actions)
            total_ships_sent = 0
            for a in actions:
                if a and len(a) >= 3:
                    total_ships_sent += int(a[2])
            avg_fleet_size = total_ships_sent / max(1, n_launches)
            multi_launch = 1.0 if n_launches > 1 else 0.0

            action_stats = np.array([
                n_launches, total_ships_sent, avg_fleet_size, multi_launch
            ], dtype=np.float32)

            # --- Delta label (ship count change over next 15 turns) ---
            future_step = min(step_idx + 15, n_steps - 1)
            future_obs = steps[future_step][agent_idx].get("observation", {})
            if future_obs and future_obs.get("planets"):
                future_total = 0
                fp_id = future_obs.get("player", player_id)
                for p in future_obs["planets"]:
                    if int(p[1]) == fp_id:
                        future_total += int(p[5])
                for fl in future_obs.get("fleets", []):
                    if int(fl[1]) == fp_id:
                        future_total += int(fl[6])
                delta = (future_total - total_my) / max(1.0, float(total_my))
            else:
                delta = 0.0

            rows.append({
                "features": features,
                "y_win": final_rewards[agent_idx],
                "y_delta": np.float32(delta),
                "action_stats": action_stats,
                "game_step": game_step,
                "player_id": player_id,
            })

    return rows


def main():
    # Find all full-game replay JSONs (>500KB, not agent logs)
    pattern = os.path.join(REPLAYS_DIR, "*.json")
    files = sorted(glob.glob(pattern))

    # Filter: full games are >500KB, agent logs contain a dash before .json
    import re
    full_games = []
    for f in files:
        size = os.path.getsize(f)
        basename = os.path.basename(f)
        # Skip agent-specific logs like 75194103-0.json
        if re.search(r"-\d+\.json$", basename):
            continue
        if size > 500_000:
            full_games.append(f)

    print(f"Found {len(full_games)} full game replays")

    all_X = []
    all_y_win = []
    all_y_delta = []
    all_action_stats = []
    all_game_ids = []
    all_player_ids = []
    all_turns = []

    for game_idx, filepath in enumerate(full_games):
        basename = os.path.basename(filepath)
        try:
            rows = extract_features_from_replay(filepath)
            for row in rows:
                all_X.append(row["features"])
                all_y_win.append(row["y_win"])
                all_y_delta.append(row["y_delta"])
                all_action_stats.append(row["action_stats"])
                all_game_ids.append(game_idx)
                all_player_ids.append(row["player_id"])
                all_turns.append(row["game_step"])
            print(f"  [{game_idx+1}/{len(full_games)}] {basename}: {len(rows)} rows")
        except Exception as e:
            print(f"  [{game_idx+1}/{len(full_games)}] {basename}: ERROR {e}")

    X = np.stack(all_X)
    y_win = np.array(all_y_win, dtype=np.float32)
    y_delta = np.array(all_y_delta, dtype=np.float32)
    action_stats = np.stack(all_action_stats)
    game_ids = np.array(all_game_ids, dtype=np.int32)
    player_ids = np.array(all_player_ids, dtype=np.int32)
    turns = np.array(all_turns, dtype=np.int32)

    np.savez_compressed(OUTPUT_FILE,
                        X=X, y_win=y_win, y_delta=y_delta,
                        action_stats=action_stats,
                        game_ids=game_ids, player_ids=player_ids,
                        turns=turns)

    print(f"\nSaved {X.shape[0]} rows × {X.shape[1]} features to {OUTPUT_FILE}")
    print(f"  Win rate in data: {y_win.mean():.3f}")
    print(f"  Mean delta: {y_delta.mean():.3f}")

    # Quick winner vs loser action comparison
    winner_mask = y_win == 1.0
    loser_mask = y_win == 0.0
    print(f"\n--- Winner action profiles ---")
    print(f"  Avg launches/turn: {action_stats[winner_mask, 0].mean():.2f}")
    print(f"  Avg fleet size:    {action_stats[winner_mask, 2].mean():.1f}")
    print(f"  Multi-launch %:    {100 * action_stats[winner_mask, 3].mean():.1f}%")
    print(f"\n--- Loser action profiles ---")
    print(f"  Avg launches/turn: {action_stats[loser_mask, 0].mean():.2f}")
    print(f"  Avg fleet size:    {action_stats[loser_mask, 2].mean():.1f}")
    print(f"  Multi-launch %:    {100 * action_stats[loser_mask, 3].mean():.1f}%")


if __name__ == "__main__":
    main()
