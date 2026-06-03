"""
Analyze V7 vs V13 decision patterns.
Runs games and collects per-turn statistics:
  - Fleet launches per turn
  - Average fleet size
  - Reserve retention rate
  - Planet count trajectory
  - Expansion vs attack ratio
"""
import math
import sys
import time
from collections import defaultdict, namedtuple
from kaggle_environments import make

Planet = namedtuple("Planet", "id owner x y radius ships production")
Fleet = namedtuple("Fleet", "id owner x y angle from_planet_id ships")

def analyze_game(agents, seed, labels):
    """Run one game and extract per-player statistics."""
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(agents)
    
    num_players = len(agents)
    stats = {i: {
        "label": labels[i],
        "planets_over_time": [],
        "ships_over_time": [],
        "fleets_launched_per_turn": [],
        "fleet_sizes": [],
        "attacks_on_neutral": 0,
        "attacks_on_enemy": 0,
        "total_ships_sent": 0,
        "total_ships_held": 0,
    } for i in range(num_players)}
    
    prev_fleet_ids = {i: set() for i in range(num_players)}
    
    for step_idx in range(len(env.steps)):
        step_data = env.steps[step_idx]
        
        for player in range(num_players):
            obs = step_data[player].get("observation") if isinstance(step_data[player], dict) else getattr(step_data[player], "observation", None)
            if obs is None:
                continue
            
            raw_planets = obs.get("planets", []) if isinstance(obs, dict) else getattr(obs, "planets", [])
            raw_fleets = obs.get("fleets", []) if isinstance(obs, dict) else getattr(obs, "fleets", [])
            
            planets = [Planet(*p) for p in raw_planets]
            fleets = [Fleet(*f) for f in raw_fleets]
            
            # Count planets and ships
            my_planets = [p for p in planets if p.owner == player]
            my_ships = sum(p.ships for p in my_planets)
            my_fleet_ships = sum(f.ships for f in fleets if f.owner == player)
            
            stats[player]["planets_over_time"].append(len(my_planets))
            stats[player]["ships_over_time"].append(my_ships + my_fleet_ships)
            stats[player]["total_ships_held"] += my_ships
            
            # Track new fleets
            current_ids = set()
            new_fleets_this_turn = []
            for f in fleets:
                current_ids.add(f.id)
                if f.owner == player and f.id not in prev_fleet_ids[player]:
                    new_fleets_this_turn.append(f)
            
            stats[player]["fleets_launched_per_turn"].append(len(new_fleets_this_turn))
            
            for f in new_fleets_this_turn:
                stats[player]["fleet_sizes"].append(f.ships)
                stats[player]["total_ships_sent"] += f.ships
                
                # Determine target type
                ux = math.cos(f.angle)
                uy = math.sin(f.angle)
                best_target = None
                best_score = float("inf")
                for p in planets:
                    if p.id == f.from_planet_id:
                        continue
                    dx = p.x - f.x
                    dy = p.y - f.y
                    d = math.hypot(dx, dy)
                    if d < 1.0:
                        continue
                    dot = (dx * ux + dy * uy) / d
                    if dot > 0.85:
                        score = d * (1.0 - dot + 0.01)
                        if score < best_score:
                            best_score = score
                            best_target = p
                
                if best_target:
                    if best_target.owner == -1:
                        stats[player]["attacks_on_neutral"] += 1
                    else:
                        stats[player]["attacks_on_enemy"] += 1
            
            prev_fleet_ids[player] = current_ids
    
    # Final result
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(num_players)]
    
    return stats, rewards


def print_stats(stats, rewards):
    for player, s in stats.items():
        fleet_sizes = s["fleet_sizes"] or [0]
        launches = s["fleets_launched_per_turn"]
        planets = s["planets_over_time"]
        ships = s["ships_over_time"]
        
        print(f"\n  [{s['label']}] (Player {player}) reward={rewards[player]}")
        print(f"    Peak planets: {max(planets) if planets else 0}, Final: {planets[-1] if planets else 0}")
        print(f"    Peak ships: {max(ships) if ships else 0}, Final: {ships[-1] if ships else 0}")
        print(f"    Total fleets launched: {sum(launches)}")
        print(f"    Avg fleet size: {sum(fleet_sizes)/len(fleet_sizes):.1f}")
        print(f"    Median fleet size: {sorted(fleet_sizes)[len(fleet_sizes)//2]:.0f}")
        print(f"    Max fleet size: {max(fleet_sizes)}")
        print(f"    Attacks on neutral: {s['attacks_on_neutral']}")
        print(f"    Attacks on enemy: {s['attacks_on_enemy']}")
        total_sent = s["total_ships_sent"]
        total_held = s["total_ships_held"]
        if total_sent + total_held > 0:
            print(f"    Aggression ratio: {total_sent/(total_sent+total_held)*100:.1f}% sent")
        
        # Early game (first 60 turns)
        early_launches = sum(launches[:60])
        early_neutral = 0
        # Approximate early neutral attacks
        print(f"    Early-game launches (t<60): {early_launches}")


def main():
    seeds = [42, 99, 137, 256, 333, 500, 777, 1024]
    
    print("=" * 60)
    print("V7 vs V13: HEAD-TO-HEAD DUEL ANALYSIS")
    print("=" * 60)
    
    for seed in seeds[:4]:
        print(f"\n--- Seed {seed} ---")
        stats, rewards = analyze_game(
            ["d:/Juracan/main_v7.py", "d:/Juracan/main_v13.py"],
            seed, ["V7", "V13"]
        )
        print_stats(stats, rewards)
    
    print("\n" + "=" * 60)
    print("4-PLAYER FFA ANALYSIS")
    print("=" * 60)
    
    for seed in seeds[:4]:
        print(f"\n--- Seed {seed} ---")
        stats, rewards = analyze_game(
            ["d:/Juracan/main_v7.py", "d:/Juracan/main_v13.py",
             "d:/Juracan/main_v10.py", "random"],
            seed, ["V7", "V13", "V10", "Random"]
        )
        print_stats(stats, rewards)


if __name__ == "__main__":
    main()
