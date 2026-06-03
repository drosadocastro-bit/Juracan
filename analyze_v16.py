"""
Analyze V16 locally across more seeds to understand its failure.
"""
from kaggle_environments import make

def analyze_v16():
    print("=" * 60)
    print("ANALYZING V16 vs V7 (Turtle Baseline)")
    print("=" * 60)
    
    seeds = range(100, 115)
    v16_wins = 0
    v7_wins = 0
    
    for seed in seeds:
        env = make("orbit_wars", debug=True, configuration={"seed": seed})
        env.run(["d:/Juracan/main_v16.py", "d:/Juracan/main_v7.py"])
        
        final = env.steps[-1]
        r16, r7 = final[0].reward, final[1].reward
        
        if r16 > r7:
            v16_wins += 1
            w = "V16"
        else:
            v7_wins += 1
            w = "V7"
            
        # Parse stances
        stances = []
        for step in env.steps:
            if step[0].status == "ACTIVE" and "stderr" in step[0]:
                for line in step[0].stderr.split('\n'):
                    if "Stance:" in line:
                        stances.append(line.split("Stance:")[1].strip())
        
        stance_counts = {s: stances.count(s) for s in set(stances)}
        
        print(f"Seed {seed}: Winner={w} | V16 Stances: {stance_counts}")

    print(f"\nFinal vs V7 -> V16: {v16_wins}, V7: {v7_wins}")

if __name__ == "__main__":
    analyze_v16()
