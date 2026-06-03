import os
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

competition = 'orbit-wars'
submissions = api.competition_submissions(competition)

submissions.sort(key=lambda x: x.date, reverse=True)

print("Submissions list:")
for sub in submissions:
    score = getattr(sub, 'public_score', 'N/A')
    print(f"ID: {sub.ref} | File: {sub.file_name} | Date: {sub.date} | Score: {score} | Description: {sub.description}")
