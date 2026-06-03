import os
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from orbit_env import OrbitWarsEnv

def main():
    print("Initializing V53 Hybrid RL Training Pipeline...")
    
    # Create vectorized environment for faster training
    # Training against V49 as the opponent
    env = make_vec_env(lambda: OrbitWarsEnv(opponent="main_v49.py"), n_envs=4)

    # Initialize PPO Agent
    model = PPO(
        "MlpPolicy", 
        env, 
        verbose=1,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=64,
        gamma=0.99
    )

    print("Starting Training (This will take a while)...")
    # Train for 50,000 steps (Very small for RL, but enough to see if it learns anything)
    model.learn(total_timesteps=50000)

    # Save the model
    os.makedirs("models", exist_ok=True)
    model.save("models/v53_ppo_model")
    print("Model saved to models/v53_ppo_model.zip")

if __name__ == "__main__":
    main()
