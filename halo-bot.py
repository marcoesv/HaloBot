import requests
import re
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
ENDPOINT = os.getenv("ENDPOINT")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")
API_VERSION = os.getenv("API_VERSION")

HALO_URL = os.getenv("HALO_URL")
HALO_ACCESS_TOKEN = os.getenv("HALO_ACCESS_TOKEN")

headers = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

# State management
class TicketState:
    def __init__(self):
        self.pending_ticket = None
        self.awaiting_confirmation = False

ticket_state = TicketState()

conversation = [{
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
- Impact (165): 1=Global/VIP, 2=Regional, 3=Plant/Department, 4=Individual User
- Urgency (166): 1=Unable to work, 2=Workaround exists, 3=Interferes with work, 4=Would assist work

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
- if the user asks for you to choose fields, choose with the current context of their messages and respond with your decisions.
"""
}]

def extract_json_from_reply(text):
    match = re.search(r"json\s*(\[\{.*?\}\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception as e:
            print("❌ Failed to parse JSON:", e)
            return None
    return None

def send_ticket_to_halo(ticket):
    headers = {
        "Authorization": f"Bearer {HALO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.post(HALO_URL, headers=headers, json=[ticket])
    if response.status_code == 201:
        result = response.json()
        ticket_id = result.get('id', 'N/A')
        print(f"✅ Ticket created successfully with ID #{ticket_id}")
        if ticket_id != 'N/A':
            print(f"🔗 View your ticket progress: https://nemakmxdev.haloitsm.com/ticket?id={ticket_id}&showmenu=true")
        return True
    else:
        print(f"❌ Failed to create ticket: {response.status_code}")
        print(response.text)
        return False

def chat(messages):
    url = f"{ENDPOINT}openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version={API_VERSION}"
    payload = {
        "messages": messages,
        "max_completion_tokens": 2000
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None

def is_confirmation(user_input):
    """Check if user input is a confirmation"""
    confirmation_words = ['yes', 'y', 'ok', 'okay', 'confirm', 'submit', 'send', 'create']
    rejection_words = ['no', 'n', 'cancel', 'abort', 'stop']
    
    user_lower = user_input.lower().strip()
    
    if any(word in user_lower for word in confirmation_words):
        return True
    elif any(word in user_lower for word in rejection_words):
        return False
    else:
        return None

def handle_bot_response(reply):
    """Handle bot response and manage ticket state - MODIFIED to always show JSON"""
    
    # Check if bot is ready to create ticket
    if "READY_TO_CREATE_TICKET" in reply:
        # Extract and store the JSON
        ticket_json = extract_json_from_reply(reply)
        if ticket_json:
            ticket_state.pending_ticket = ticket_json[0]
            ticket_state.awaiting_confirmation = True
            
            # MODIFIED: Show the FULL response including JSON instead of hiding it
            print(f"Bot: {reply}")
            print("\n🔄 Does this look correct? Type 'yes' to submit the ticket or 'no' to cancel.")
            return
    
    # Regular response
    print(f"Bot: {reply}")

# Main loop
while True:
    user_input = input("You: ")
    
    # Check if we're awaiting confirmation
    if ticket_state.awaiting_confirmation:
        confirmation = is_confirmation(user_input)
        if confirmation is True:
            if send_ticket_to_halo(ticket_state.pending_ticket):
                print("🎫 Your ticket has been submitted to the IT support team!")
            ticket_state.pending_ticket = None
            ticket_state.awaiting_confirmation = False
            continue
        elif confirmation is False:
            print("❌ Ticket creation cancelled.")
            ticket_state.pending_ticket = None
            ticket_state.awaiting_confirmation = False
            continue
    
    # Regular conversation flow
    conversation.append({"role": "user", "content": user_input})
    reply = chat(conversation)
    
    if reply:
        conversation.append({"role": "assistant", "content": reply})
        handle_bot_response(reply)