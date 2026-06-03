"""V11 smoke test: duel + FFA vs V10/V7."""
from kaggle_environments import make

print("=== V11 vs V10: 2-player duel ===")
duel = []
for seed in [42, 99, 137, 256]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v11.py", "d:/Juracan/main_v10.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V11" if r0 > r1 else ("V10" if r1 > r0 else "TIE")
    duel.append(w)
    print(f"  seed={seed}: V11={r0} V10={r1} winner={w}")
print(f"Duel: V11={duel.count('V11')}, V10={duel.count('V10')}")

print("\n=== V11 vs V7: 2-player duel ===")
duel2 = []
for seed in [42, 99, 137, 256]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v11.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V11" if r0 > r1 else ("V7" if r1 > r0 else "TIE")
    duel2.append(w)
    print(f"  seed={seed}: V11={r0} V7={r1} winner={w}")
print(f"Duel: V11={duel2.count('V11')}, V7={duel2.count('V7')}")

print("\n=== 4-player FFA ===")
ffa = []
for seed in [42, 99, 137, 256]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v11.py", "d:/Juracan/main_v10.py",
             "d:/Juracan/main_v7.py", "random"])
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(4)]
    names = ["V11", "V10", "V7", "random"]
    wi = rewards.index(max(rewards))
    w = names[wi]
    ffa.append(w)
    print(f"  seed={seed}: rewards={rewards} winner={w}")
for n in names:
    print(f"  {n}: {ffa.count(n)}/4")
