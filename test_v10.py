"""Analyze action/observation space for RL design."""
from kaggle_environments import make

env = make("orbit_wars", debug=True, configuration={"seed": 42})
env.run(["d:/Juracan/main_v10.py", "random"])

# Check mid-game
step = env.steps[50]
obs = step[0]["observation"]
print("=== Observation space ===")
planets = obs["planets"]
fleets = obs["fleets"]
print("Planets:", len(planets), "(each: [id,owner,x,y,radius,ships,prod])")
print("Fleets:", len(fleets), "(each: [id,owner,x,y,angle,from_planet_id,ships])")
print("Step:", obs["step"])
print("Player:", obs["player"])
print("Angular vel:", obs["angular_velocity"])
print()

# Action space
actions = step[0].get("action", [])
print("=== Action space ===")
print("Actions this turn:", len(actions))
for a in (actions or [])[:3]:
    print(f"  [planet_id={a[0]}, angle={a[1]:.3f}, ships={a[2]}]")
print()

# Dimensions across game
print("=== Key dimensions across all steps ===")
max_planets = 0
max_fleets = 0
max_actions = 0
total_actions = 0
active_turns = 0
for i in range(1, len(env.steps)):
    p_count = len(env.steps[i][0]["observation"]["planets"])
    f_count = len(env.steps[i][0]["observation"]["fleets"])
    a = env.steps[i][0].get("action", []) or []
    max_planets = max(max_planets, p_count)
    max_fleets = max(max_fleets, f_count)
    max_actions = max(max_actions, len(a))
    total_actions += len(a)
    if len(a) > 0:
        active_turns += 1

print(f"Max planets: {max_planets}")
print(f"Max fleets: {max_fleets}")
print(f"Max actions/turn: {max_actions}")
print(f"Avg actions/active turn: {total_actions / max(1, active_turns):.2f}")
print(f"Active turns: {active_turns}/{len(env.steps)}")
print(f"Config: {dict(env.configuration)}")
print()

# Check what a typical planet looks like
print("=== Sample planet ===")
for p in planets[:3]:
    print(f"  id={p[0]} owner={p[1]} x={p[2]:.1f} y={p[3]:.1f} r={p[4]:.1f} ships={p[5]} prod={p[6]}")

# Count how many planets appear across all games
print()
print("=== Board summary ===")
p0 = env.steps[1][0]["observation"]["planets"]
owners = {}
for p in p0:
    o = p[1]
    owners[o] = owners.get(o, 0) + 1
for o in sorted(owners):
    label = {-1: "neutral", 0: "player0", 1: "player1"}.get(o, f"player{o}")
    print(f"  {label}: {owners[o]} planets")
