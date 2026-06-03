import os
import math
import numpy as np

# Lazy-load the model so it doesn't crash if imported briefly
_model = None

def get_model():
    global _model
    if _model is None:
        from stable_baselines3 import PPO
        model_path = os.path.join(os.path.dirname(__file__), "models", "v53_ppo_model.zip")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"RL model not found at {model_path}")
        _model = PPO.load(model_path)
    return _model

def _process_obs(obs):
    # Determine if obs is dict or object
    if isinstance(obs, dict):
        player_id = obs.get("player", 0)
        planets_raw = obs.get("planets", [])
    else:
        player_id = obs.player
        planets_raw = obs.planets
        
    processed = [float(player_id)]
    planets_dict = {p[0]: p for p in planets_raw}
    
    for pid in range(100):
        if pid in planets_dict:
            p = planets_dict[pid]
            owner = p[1]
            if owner == -1: owner_val = 0.0
            elif owner == player_id: owner_val = 1.0
            else: owner_val = -1.0
            
            processed.extend([
                owner_val, 
                p[2] / 100.0,
                p[3] / 100.0,
                p[5] / 100.0
            ])
        else:
            processed.extend([0.0, 0.0, 0.0, 0.0])
            
    return np.array(processed, dtype=np.float32)

def agent(obs, config=None):
    model = get_model()
    
    if isinstance(obs, dict):
        player_id = obs.get("player", 0)
        planets_raw = obs.get("planets", [])
    else:
        player_id = obs.player
        planets_raw = obs.planets
        
    obs_array = _process_obs(obs)
    # Get action from RL policy
    action, _states = model.predict(obs_array, deterministic=True)
    target_id = int(action)
    
    moves = []
    my_planets = [p for p in planets_raw if p[1] == player_id]
    target_planet = next((p for p in planets_raw if p[0] == target_id), None)
    
    # Very simple heuristic execution for the RL macro decision
    if my_planets and target_planet and target_planet[1] != player_id:
        source = max(my_planets, key=lambda p: p[5])
        dx = target_planet[2] - source[2]
        dy = target_planet[3] - source[3]
        angle = math.atan2(dy, dx)
        ships = max(1, source[5] // 2)
        moves.append([source[0], angle, ships])
        
    return moves
