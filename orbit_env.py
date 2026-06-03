import gymnasium as gym
from gymnasium import spaces
import numpy as np
from kaggle_environments import make
import math

class OrbitWarsEnv(gym.Env):
    """
    Gymnasium wrapper for Orbit Wars.
    Trains an agent to pick the optimal TARGET planet.
    A simple heuristic picks the SOURCE planet and launches ships.
    """
    def __init__(self, opponent="main_v49.py"):
        super().__init__()
        self.kaggle_env = make("orbit_wars", debug=False)
        # Train against 3 opponents (4 player FFA)
        self.trainer = self.kaggle_env.train([None, opponent, opponent, opponent])
        
        # Action: pick target planet ID (0-99)
        self.action_space = spaces.Discrete(100)
        
        # Obs: Player ID (1) + 100 planets * 4 features (owner, x, y, ships) = 401
        self.observation_space = spaces.Box(low=-10.0, high=10.0, shape=(401,), dtype=np.float32)
        self.last_obs = None
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        obs = self.trainer.reset()
        self.last_obs = obs
        return self._process_obs(obs), {}

    def _process_obs(self, obs):
        player_id = obs['player']
        processed = [float(player_id)]
        
        # Ensure we always have 100 planets in a fixed order
        planets_dict = {p[0]: p for p in obs['planets']}
        
        for pid in range(100):
            if pid in planets_dict:
                p = planets_dict[pid]
                owner = p[1]
                if owner == -1: owner_val = 0.0
                elif owner == player_id: owner_val = 1.0
                else: owner_val = -1.0
                
                processed.extend([
                    owner_val, 
                    p[2] / 100.0,  # x
                    p[3] / 100.0,  # y
                    p[5] / 100.0   # ships
                ])
            else:
                # Padding if planet doesn't exist (though in Orbit Wars there are exactly 100)
                processed.extend([0.0, 0.0, 0.0, 0.0])
                
        return np.array(processed, dtype=np.float32)
        
    def step(self, action):
        target_id = int(action)
        moves = []
        
        if self.last_obs is not None:
            my_planets = [p for p in self.last_obs['planets'] if p[1] == self.last_obs['player']]
            target_planet = None
            for p in self.last_obs['planets']:
                if p[0] == target_id:
                    target_planet = p
                    break
                    
            if my_planets and target_planet and target_planet[1] != self.last_obs['player']:
                # Heuristic: Find our planet with the most ships to attack the target
                source = max(my_planets, key=lambda p: p[5])
                
                # Simple aim (straight line, no comet dodging for this demo wrapper)
                dx = target_planet[2] - source[2]
                dy = target_planet[3] - source[3]
                angle = math.atan2(dy, dx)
                ships = max(1, source[5] // 2) # Send half our ships
                
                moves.append([source[0], angle, ships])
                
        obs, reward, done, info = self.trainer.step(moves)
        self.last_obs = obs
        
        # Reward shaping
        final_reward = 0.0
        if done:
            if reward == 1:
                final_reward = 100.0
            else:
                final_reward = -10.0
                
        return self._process_obs(obs), final_reward, done, False, {}
