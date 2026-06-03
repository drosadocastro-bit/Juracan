"""V16 smoke test."""
from kaggle_environments import make

print("=== V16 vs V7: 2-player duel ===")
duel = []
for seed in [42, 99, 137, 256]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v16.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V16" if r0 > r1 else ("V7" if r1 > r0 else "TIE")
    duel.append(w)
    print(f"  seed={seed}: V16={r0} V7={r1} winner={w}")
print(f"Duel vs V7: V16={duel.count('V16')}, V7={duel.count('V7')}, TIE={duel.count('TIE')}")

print("\n=== V16 vs V10: 2-player duel ===")
duel2 = []
for seed in [42, 99, 137, 256]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v16.py", "d:/Juracan/main_v10.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V16" if r0 > r1 else ("V10" if r1 > r0 else "TIE")
    duel2.append(w)
    print(f"  seed={seed}: V16={r0} V10={r1} winner={w}")
print(f"Duel vs V10: V16={duel2.count('V16')}, V10={duel2.count('V10')}, TIE={duel2.count('TIE')}")
