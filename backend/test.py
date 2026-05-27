import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3",
        "prompt": "Say hello",
        "stream": False
    }
)

print(response.json())
