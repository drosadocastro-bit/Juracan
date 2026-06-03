import os
import requests
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

episode_id = 75825868
url = f"https://www.kaggle.com/api/v1/competitions/episodes/replay/{episode_id}"

response = api.process_response(api.api_client.call_api(
    '/competitions/episodes/replay/{episodeId}', 'GET',
    path_params={'episodeId': episode_id},
    auth_settings=['kaggleTokenAuth'],
    _return_http_data_only=True
))

with open(f"d:/Juracan/replays/replay_{episode_id}.json", "wb") as f:
    f.write(response)

print(f"Downloaded replay_{episode_id}.json")
