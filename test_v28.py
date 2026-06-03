"""V28 PV Scoring — gauntlet vs V27.1, V20, V7."""
from kaggle_environments import make

print("=" * 60)
print("V28 vs V27.1: 2-player duel (6 seeds)")
print("=" * 60)
duel_v27 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v28.py", "d:/Juracan/main_v27_1.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V28" if r0 > r1 else ("V27.1" if r1 > r0 else "TIE")
    duel_v27.append(w)
    print(f"  seed={seed}: V28={r0} V27.1={r1} winner={w}")
print(f"\nDuel vs V27.1: V28={duel_v27.count('V28')}, V27.1={duel_v27.count('V27.1')}, TIE={duel_v27.count('TIE')}")

print("\n" + "=" * 60)
print("V28 vs V20: 2-player duel (6 seeds)")
print("=" * 60)
duel_v20 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v28.py", "d:/Juracan/main_v20.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V28" if r0 > r1 else ("V20" if r1 > r0 else "TIE")
    duel_v20.append(w)
    print(f"  seed={seed}: V28={r0} V20={r1} winner={w}")
print(f"\nDuel vs V20: V28={duel_v20.count('V28')}, V20={duel_v20.count('V20')}, TIE={duel_v20.count('TIE')}")

print("\n" + "=" * 60)
print("V28 vs V27.1 vs V20 vs V7: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V28", "V27.1", "V20", "V7"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v28.py", "d:/Juracan/main_v27_1.py",
             "d:/Juracan/main_v20.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(4)]
    wi = rewards.index(max(rewards))
    w = names[wi]
    ffa.append(w)
    print(f"  seed={seed}: rewards={rewards} winner={w}")

print(f"\nFFA Record:")
for n in names:
    print(f"  {n}: {ffa.count(n)}/6")

print("\n" + "=" * 60)
print("V28 GAUNTLET SUMMARY")
print("=" * 60)
print(f"  vs V27.1 (duel): {duel_v27.count('V28')}-{duel_v27.count('V27.1')} (TIE={duel_v27.count('TIE')})")
print(f"  vs V20 (duel):   {duel_v20.count('V28')}-{duel_v20.count('V20')} (TIE={duel_v20.count('TIE')})")
print(f"  FFA:             V28={ffa.count('V28')}/6")
