import os
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

submission_id = 52297594
episodes = api.competition_episodes(submission_id)

for ep in episodes[:10]:
    # ep is an Episode object
    # We need to find the reward for OUR agent in this episode
    # But the Episode object doesn't have agents info directly?
    # Let's try to get more info
    print(f"ID: {ep.id}, Type: {ep.type}, Date: {ep.createTime}")
