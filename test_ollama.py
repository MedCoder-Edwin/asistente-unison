
import requests

url = "http://localhost:11434/api/generate"

payload = {
    "model": "qwen2.5:7b-instruct",
    "prompt": "Explica brevemente qué es un reglamento universitario.",
    "stream": False
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    result = response.json()
    print("\nRespuesta del modelo:\n")
    print(result["response"])
else:
    print("Error:", response.status_code, response.text)
