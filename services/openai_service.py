import os
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
ENDPOINT = os.getenv("ENDPOINT")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")
API_VERSION = os.getenv("API_VERSION")

headers_openai = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

async def call_openai(messages):
    """Make an async call to Azure OpenAI API"""
    url = f"{ENDPOINT}openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version={API_VERSION}"
    payload = {
        "messages": messages,
        "max_completion_tokens": 2000
    }
    # Use asyncio.to_thread to call blocking requests.post in async context
    response = await asyncio.to_thread(requests.post, url, headers=headers_openai, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None
