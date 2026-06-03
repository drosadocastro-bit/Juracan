"""V27.1 Calibrated Fleet Doctrine — gauntlet vs V20, V7."""
from kaggle_environments import make

print("=" * 60)
print("V27.1 vs V20: 2-player duel (6 seeds)")
print("=" * 60)
duel_v20 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v27_1.py", "d:/Juracan/main_v20.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V27.1" if r0 > r1 else ("V20" if r1 > r0 else "TIE")
    duel_v20.append(w)
    print(f"  seed={seed}: V27.1={r0} V20={r1} winner={w}")
print(f"\nDuel vs V20: V27.1={duel_v20.count('V27.1')}, V20={duel_v20.count('V20')}, TIE={duel_v20.count('TIE')}")

print("\n" + "=" * 60)
print("V27.1 vs V7: 2-player duel (6 seeds)")
print("=" * 60)
duel_v7 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v27_1.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V27.1" if r0 > r1 else ("V7" if r1 > r0 else "TIE")
    duel_v7.append(w)
    print(f"  seed={seed}: V27.1={r0} V7={r1} winner={w}")
print(f"\nDuel vs V7: V27.1={duel_v7.count('V27.1')}, V7={duel_v7.count('V7')}, TIE={duel_v7.count('TIE')}")

print("\n" + "=" * 60)
print("V27.1 vs V20 vs V7 vs random: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V27.1", "V20", "V7", "random"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v27_1.py", "d:/Juracan/main_v20.py",
             "d:/Juracan/main_v7.py", "random"])
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
print("V27.1 GAUNTLET SUMMARY")
print("=" * 60)
print(f"  vs V20 (duel):  {duel_v20.count('V27.1')}-{duel_v20.count('V20')} (TIE={duel_v20.count('TIE')})")
print(f"  vs V7 (duel):   {duel_v7.count('V27.1')}-{duel_v7.count('V7')} (TIE={duel_v7.count('TIE')})")
print(f"  FFA:            V27.1={ffa.count('V27.1')}/6")
