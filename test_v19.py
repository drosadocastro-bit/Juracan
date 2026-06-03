"""V19 smoke test — 10 seeds duel + 4 seeds FFA."""
from kaggle_environments import make

print("=" * 60)
print("V19 vs V7: 2-player duel (10 seeds)")
print("=" * 60)
duel = []
for seed in range(42, 52):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v19.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V19" if r0 > r1 else ("V7" if r1 > r0 else "TIE")
    duel.append(w)
    print(f"  seed={seed}: V19={r0} V7={r1} winner={w}")
print(f"\nDuel Record: V19={duel.count('V19')}, V7={duel.count('V7')}, TIE={duel.count('TIE')}")

print("\n" + "=" * 60)
print("V19 vs V7 vs V10 vs random: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V19", "V7", "V10", "random"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v19.py", "d:/Juracan/main_v7.py",
             "d:/Juracan/main_v10.py", "random"])
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(4)]
    wi = rewards.index(max(rewards))
    w = names[wi]
    ffa.append(w)
    print(f"  seed={seed}: rewards={rewards} winner={w}")
print(f"\nFFA Record:")
for n in names:
    print(f"  {n}: {ffa.count(n)}/6")
