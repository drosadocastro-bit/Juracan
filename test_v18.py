"""V18 smoke test vs V7."""
from kaggle_environments import make

print("=== V18 vs V7: 2-player duel ===")
duel = []
for seed in [42, 99, 137, 256, 512]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v18.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V18" if r0 > r1 else ("V7" if r1 > r0 else "TIE")
    duel.append(w)
    print(f"  seed={seed}: V18={r0} V7={r1} winner={w}")
print(f"Duel vs V7: V18={duel.count('V18')}, V7={duel.count('V7')}, TIE={duel.count('TIE')}")

print("\n=== 4-player FFA ===")
ffa = []
for seed in [42, 99, 137, 256]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v18.py", "d:/Juracan/main_v7.py",
             "d:/Juracan/main_v10.py", "random"])
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(4)]
    names = ["V18", "V7", "V10", "random"]
    wi = rewards.index(max(rewards))
    w = names[wi]
    ffa.append(w)
    print(f"  seed={seed}: rewards={rewards} winner={w}")
for n in names:
    print(f"  {n}: {ffa.count(n)}/4")
