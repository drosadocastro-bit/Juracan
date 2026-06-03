import requests
import json
import os

username = "drakus74"
key = "b6b11c72a4d77f555cec0fd71bf7e826"

episode_id = 75825868

if not os.path.exists("d:/Juracan/logs"):
    os.makedirs("d:/Juracan/logs")

for i in range(4):
    url = f"https://www.kaggle.com/api/v1/competitions/episodes/agent/logs/{episode_id}/{i}"
    response = requests.get(url, auth=(username, key))
    if response.status_code == 200:
        with open(f"d:/Juracan/logs/log_{episode_id}_{i}.jsonl", "wb") as f:
            f.write(response.content)
        print(f"Downloaded log_{episode_id}_{i}.jsonl")
    else:
        print(f"Failed index {i}: {response.status_code} - {response.text}")
