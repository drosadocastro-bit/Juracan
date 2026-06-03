"""V26 gauntlet — V7, V20, V25."""
from kaggle_environments import make

print("=" * 60)
print("V26 vs V20: 2-player duel (6 seeds)")
print("=" * 60)
duel_v20 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v26.py", "d:/Juracan/main_v20.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V26" if r0 > r1 else ("V20" if r1 > r0 else "TIE")
    duel_v20.append(w)
    print(f"  seed={seed}: V26={r0} V20={r1} winner={w}")
print(f"\nDuel vs V20: V26={duel_v20.count('V26')}, V20={duel_v20.count('V20')}, TIE={duel_v20.count('TIE')}")

print("\n" + "=" * 60)
print("V26 vs V7: 2-player duel (6 seeds)")
print("=" * 60)
duel_v7 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v26.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V26" if r0 > r1 else ("V7" if r1 > r0 else "TIE")
    duel_v7.append(w)
    print(f"  seed={seed}: V26={r0} V7={r1} winner={w}")
print(f"\nDuel vs V7: V26={duel_v7.count('V26')}, V7={duel_v7.count('V7')}, TIE={duel_v7.count('TIE')}")

print("\n" + "=" * 60)
print("V26 vs V25 vs V20 vs V7: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V26", "V25", "V20", "V7"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v26.py", "d:/Juracan/main_v25.py",
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
print("V26 GAUNTLET SUMMARY")
print("=" * 60)
print(f"  vs V20:  {duel_v20.count('V26')}-{duel_v20.count('V20')} (TIE={duel_v20.count('TIE')})")
print(f"  vs V7:   {duel_v7.count('V26')}-{duel_v7.count('V7')} (TIE={duel_v7.count('TIE')})")
print(f"  FFA:     V26={ffa.count('V26')}/6")
