"""V23 smoke test."""
from kaggle_environments import make

print("=" * 60)
print("V23 vs V20: 2-player duel (6 seeds)")
print("=" * 60)
duel_v20 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v23.py", "d:/Juracan/main_v20.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V23" if r0 > r1 else ("V20" if r1 > r0 else "TIE")
    duel_v20.append(w)
    print(f"  seed={seed}: V23={r0} V20={r1} winner={w}")
print(f"\nDuel vs V20: V23={duel_v20.count('V23')}, V20={duel_v20.count('V20')}, TIE={duel_v20.count('TIE')}")

print("\n" + "=" * 60)
print("V23 vs V22: 2-player duel (6 seeds)")
print("=" * 60)
duel_v22 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v23.py", "d:/Juracan/main_v22.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V23" if r0 > r1 else ("V22" if r1 > r0 else "TIE")
    duel_v22.append(w)
    print(f"  seed={seed}: V23={r0} V22={r1} winner={w}")
print(f"\nDuel vs V22: V23={duel_v22.count('V23')}, V22={duel_v22.count('V22')}, TIE={duel_v22.count('TIE')}")

print("\n" + "=" * 60)
print("V23 vs V20 vs V7 vs random: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V23", "V20", "V7", "random"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v23.py", "d:/Juracan/main_v20.py",
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
