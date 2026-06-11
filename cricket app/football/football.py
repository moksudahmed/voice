import requests

headers = {
    "X-Auth-Token": "0f9ae9ea357046c788ad0c4c54499754"
}

response = requests.get(
    "https://api.football-data.org/v4/matches",
    headers=headers
)

print(response.json())