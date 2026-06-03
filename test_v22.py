"""V22 smoke test."""
from kaggle_environments import make

print("=" * 60)
print("V22 vs V21: 2-player duel (6 seeds)")
print("=" * 60)
duel = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v22.py", "d:/Juracan/main_v21.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V22" if r0 > r1 else ("V21" if r1 > r0 else "TIE")
    duel.append(w)
    print(f"  seed={seed}: V22={r0} V21={r1} winner={w}")
print(f"\nDuel Record: V22={duel.count('V22')}, V21={duel.count('V21')}, TIE={duel.count('TIE')}")

print("\n" + "=" * 60)
print("V22 vs V21 vs V10 vs V7: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V22", "V21", "V10", "V7"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v22.py", "d:/Juracan/main_v21.py",
             "d:/Juracan/main_v10.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(4)]
    wi = rewards.index(max(rewards))
    w = names[wi]
    ffa.append(w)
    print(f"  seed={seed}: rewards={rewards} winner={w}")
print(f"\nFFA Record:")
for n in names:
    print(f"  {n}: {ffa.count(n)}/6")
