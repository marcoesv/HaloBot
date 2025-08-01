import os
import re
import json
import requests
import asyncio
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
ENDPOINT = os.getenv("ENDPOINT")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")
API_VERSION = os.getenv("API_VERSION")

HALO_URL = os.getenv("HALO_URL")
HALO_AUTH_URL = os.getenv("HALO_AUTH_URL")
HALO_CLIENT_ID = os.getenv("HALO_CLIENT_ID")
HALO_CLIENT_SECRET = os.getenv("HALO_CLIENT_SECRET")

def get_halo_token():
    payload = {
        "client_id": HALO_CLIENT_ID,
        "client_secret": HALO_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(HALO_AUTH_URL, data=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data.get("access_token")


headers_openai = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

def extract_json_from_reply(text):
    match = re.search(r"json\s*(\[\{.*?\}\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception as e:
            print("❌ Failed to parse JSON:", e)
            return None
    return None

def send_ticket_to_halo(ticket, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(HALO_URL, headers=headers, json=[ticket])
    if response.status_code in (200, 201, 202):
        result = response.json()
        ticket_id = result.get('id', None)
        if ticket_id:
            return f"✅ Ticket created successfully with ID #{ticket_id}\n\n🔗 View your ticket progress: https://nemakmxdev.haloitsm.com/ticket?id={ticket_id}&showmenu=true"
        else:
            return "✅ Ticket created successfully!"
    else:
        return f"❌ Failed to create ticket: {response.status_code} - {response.text}"



async def call_openai(messages):
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

def is_confirmation(user_input):
    confirmation_words = ['yes', 'y', 'ok', 'okay', 'confirm', 'submit', 'send', 'create']
    rejection_words = ['no', 'n', 'cancel', 'abort', 'stop']
    
    user_lower = user_input.lower().strip()
    
    if any(word in user_lower for word in confirmation_words):
        return True
    elif any(word in user_lower for word in rejection_words):
        return False
    else:
        return None

async def process_message(user_input, state):
    if "halo_token" not in state:
        token = get_halo_token()
        state["halo_token"] = token
    
    if state.get("awaiting_confirmation"):
        confirmation = is_confirmation(user_input)
        if confirmation is True:
            ticket = state.get("pending_ticket")
            if ticket:
                result_message = send_ticket_to_halo(ticket, state["halo_token"])
                state.clear()
                return f"🎫 Your ticket has been submitted to the IT support team!\n\n{result_message}"
            else:
                state.clear()
                return "❌ Failed to submit ticket. Please try again."
        elif confirmation is False:
            state.clear()
            return "❌ Ticket creation cancelled."
        else:
            return "🔄 Please reply 'yes' to submit the ticket or 'no' to cancel."

    # Normal conversation flow
    if "conversation" not in state:
        # Initialize conversation messages with system prompt (same as your script)
        state["conversation"] = [{
            "role": "system",
            "content": """
You create tickets or answer technical troubleshooting questions. For anything else, respond: "I cannot help with that." Always respond in the user's input language.

Ticket Types:
- Incident (tickettype_id: 1): Fix problems (outages, errors, broken functionality)  
- Request (tickettype_id: 3): New services (access, software, setup)

When you have all required information to create a ticket, respond with:
1. A user-friendly summary in this format:
📋 Ticket Summary
Type: [Incident/Request]
Title: [summary]
User: [Full Name] ([email@company.com])
Description: [details without HTML tags]
Impact: [Global/VIP, Regional, Plant/Department, Individual User] 
Urgency: [Unable to work, Workaround exists, Interferes with work, Would assist work]

2. Then add: "READY_TO_CREATE_TICKET"

3. Then include the JSON with this exact structure:
json[{
 "summary": "Brief description",
 "details_html": "Detailed description with user table",
 "tickettype_id": 1,
 "team_id": 45,
 "user_id": 16404,
 "customfields": [
 {"id": 165, "value": "1"},
 {"id": 166, "value": "1"}
 ]
}]

Custom field values:
- Impact (165): Global/VIP, Regional, Plant/Department, Individual User
- Urgency (166): Unable to work, Workaround exists, Interferes with work, Would assist work

User Information Requirements:
- ALWAYS ask for user's full name and corporate email if not provided
- ALWAYS include a user information table at the TOP of details_html using this exact HTML format:
<table border="1" style="border-collapse: collapse; margin-bottom: 20px;">
<tr><td><strong>Name:</strong></td><td>[Full Name]</td></tr>
<tr><td><strong>Email:</strong></td><td>[email@nemak.com]</td></tr>
</table>

Rules:
- choose the correct impact and urgency based on the users message, and confirm with the user with the user-friendly summary
- Extract provided info, ask only for missing fields (including user name and email)
- Never create incomplete tickets
- All fields required: summary, details_html (with user table), tickettype_id, impact, urgency, user name, corporate email
"""
        }]

    state["conversation"].append({"role": "user", "content": user_input})

    reply = await call_openai(state["conversation"])

    if reply and "READY_TO_CREATE_TICKET" in reply:
        ticket_json = extract_json_from_reply(reply)
        if ticket_json:
            state["pending_ticket"] = ticket_json[0]
            state["awaiting_confirmation"] = True
            # Return the user-friendly part only
            parts = reply.split("READY_TO_CREATE_TICKET")
            return parts[0].strip() + "\n\n🔄 Does this look correct? Please reply 'yes' to submit or 'no' to cancel."
    elif reply:
        return reply
    else:
        return "Sorry, I didn't understand that. Could you please rephrase?"
