"""V29 The All-Seeing Eye — gauntlet vs V28."""
from kaggle_environments import make

print("=" * 60)
print("V29 vs V28: 2-player duel (6 seeds)")
print("=" * 60)
duel_v28 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v29.py", "d:/Juracan/main_v28.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V29" if r0 > r1 else ("V28" if r1 > r0 else "TIE")
    duel_v28.append(w)
    print(f"  seed={seed}: V29={r0} V28={r1} winner={w}")
print(f"\nDuel vs V28: V29={duel_v28.count('V29')}, V28={duel_v28.count('V28')}, TIE={duel_v28.count('TIE')}")

print("\n" + "=" * 60)
print("V29 vs V28 vs V20 vs V7: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V29", "V28", "V20", "V7"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v29.py", "d:/Juracan/main_v28.py",
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
print("V29 GAUNTLET SUMMARY")
print("=" * 60)
print(f"  vs V28 (duel):   {duel_v28.count('V29')}-{duel_v28.count('V28')} (TIE={duel_v28.count('TIE')})")
print(f"  FFA:             V29={ffa.count('V29')}/6")
