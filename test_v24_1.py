"""V24.1 smoke test — compare against V20 (champion) and V24."""
from kaggle_environments import make

print("=" * 60)
print("V24.1 vs V20: 2-player duel (6 seeds)")
print("=" * 60)
duel_v20 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24_1.py", "d:/Juracan/main_v20.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V24.1" if r0 > r1 else ("V20" if r1 > r0 else "TIE")
    duel_v20.append(w)
    print(f"  seed={seed}: V24.1={r0} V20={r1} winner={w}")
print(f"\nDuel vs V20: V24.1={duel_v20.count('V24.1')}, V20={duel_v20.count('V20')}, TIE={duel_v20.count('TIE')}")

print("\n" + "=" * 60)
print("V24.1 vs V24: 2-player duel (6 seeds)")
print("=" * 60)
duel_v24 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24_1.py", "d:/Juracan/main_v24.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V24.1" if r0 > r1 else ("V24" if r1 > r0 else "TIE")
    duel_v24.append(w)
    print(f"  seed={seed}: V24.1={r0} V24={r1} winner={w}")
print(f"\nDuel vs V24: V24.1={duel_v24.count('V24.1')}, V24={duel_v24.count('V24')}, TIE={duel_v24.count('TIE')}")

print("\n" + "=" * 60)
print("V24.1 vs V24 vs V20 vs V7: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V24.1", "V24", "V20", "V7"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24_1.py", "d:/Juracan/main_v24.py",
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
