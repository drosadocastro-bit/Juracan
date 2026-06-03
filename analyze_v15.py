"""
Analyze V15 vs V7 decision patterns and save replays.
"""
import json
import os
from kaggle_environments import make

def analyze_v15_failures():
    print("=" * 60)
    print("ANALYZING V15 (Adaptive) vs V7 (Pure Heuristic)")
    print("=" * 60)
    
    seeds = [42, 99, 137, 256]
    replays_dir = "d:/Juracan/replays"
    os.makedirs(replays_dir, exist_ok=True)
    
    losses = 0
    for seed in seeds:
        env = make("orbit_wars", debug=True, configuration={"seed": seed})
        # V15 vs V7
        env.run(["d:/Juracan/main_v15.py", "d:/Juracan/main_v7.py"])
        
        final = env.steps[-1]
        r15, r7 = final[0].reward, final[1].reward
        
        if r15 < r7:
            losses += 1
            print(f"\n[Seed {seed}] V15 LOST to V7.")
            
            # Save replay
            replay_path = os.path.join(replays_dir, f"v15_loss_seed_{seed}.html")
            with open(replay_path, "w", encoding="utf-8") as f:
                f.write(env.render(mode="html"))
            print(f"  Replay saved to: {replay_path}")
            
            # Extract basic stats
            v15_ships = [sum(p[5] for p in step[0].observation.planets if p[1] == 0) for step in env.steps[1:]]
            v7_ships = [sum(p[5] for p in step[1].observation.planets if p[1] == 1) for step in env.steps[1:]]
            
            v15_planets = [sum(1 for p in step[0].observation.planets if p[1] == 0) for step in env.steps[1:]]
            v7_planets = [sum(1 for p in step[1].observation.planets if p[1] == 1) for step in env.steps[1:]]
            
            # Find the "turning point" where V7 overtook V15 in planet count
            turning_point = None
            for step_idx in range(len(v15_planets)):
                if v7_planets[step_idx] > v15_planets[step_idx] and turning_point is None:
                    turning_point = step_idx
            
            print(f"  Final Planets -> V15: {v15_planets[-1]}, V7: {v7_planets[-1]}")
            print(f"  Peak Ships    -> V15: {max(v15_ships)}, V7: {max(v7_ships)}")
            if turning_point:
                print(f"  V7 took the lead in planets at turn {turning_point}")
                
            # Let's count stances used by V15. V15 logs "Turn X Stance: Y" to stderr
            # But debug=True captures agent logs in env.steps
            stances = []
            for step in env.steps:
                if step[0].status == "ACTIVE" and "stderr" in step[0]:
                    for line in step[0].stderr.split('\n'):
                        if "Stance:" in line:
                            stances.append(line.split("Stance:")[1].strip())
            
            if stances:
                stance_counts = {s: stances.count(s) for s in set(stances)}
                print(f"  V15 Stances used during game: {stance_counts}")

if __name__ == "__main__":
    analyze_v15_failures()
