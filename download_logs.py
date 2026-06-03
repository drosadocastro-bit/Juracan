import os
import json
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

episode_id = 75825868

# Try to get logs for index 0-3
for i in range(4):
    try:
        # This is the raw API call
        response = api.api_client.call_api(
            '/competitions/episodes/agent/logs/{episodeId}/{agentIndex}', 'GET',
            path_params={'episodeId': episode_id, 'agentIndex': i},
            auth_settings=['kaggleTokenAuth'],
            _return_http_data_only=True
        )
        if response:
            with open(f"d:/Juracan/logs/log_{episode_id}_{i}.jsonl", "wb") as f:
                f.write(response)
            print(f"Downloaded log_{episode_id}_{i}.jsonl")
    except Exception as e:
        print(f"Failed index {i}: {e}")
