import os
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

competition = 'orbit-wars'
submissions = api.competition_submissions(competition)

# Sort by date descending
submissions.sort(key=lambda x: x.date, reverse=True)

for sub in submissions[:5]:
    print(f"ID: {sub.ref}, File: {sub.file_name}, Date: {sub.date}, Score: {getattr(sub, 'public_score', 'N/A')}")
