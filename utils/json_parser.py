import re
import json

def extract_json_from_reply(text):
    """Extract JSON from OpenAI reply text"""
    match = re.search(r"json\s*(\[\{.*?\}\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception as e:
            print("❌ Failed to parse JSON:", e)
            return None
    return None
