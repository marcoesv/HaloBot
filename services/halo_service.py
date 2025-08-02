import os
import requests
from dotenv import load_dotenv

load_dotenv()

HALO_URL = os.getenv("HALO_URL")
HALO_AUTH_URL = os.getenv("HALO_AUTH_URL")
HALO_CLIENT_ID = os.getenv("HALO_CLIENT_ID")
HALO_CLIENT_SECRET = os.getenv("HALO_CLIENT_SECRET")

def get_halo_token():
    """Get authentication token for Halo ITSM API"""
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

def send_ticket_to_halo(ticket, token):
    """Send a ticket to Halo ITSM and return the result message with ticket ID"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(HALO_URL, headers=headers, json=[ticket])
    if response.status_code in (200, 201, 202):
        result = response.json()
        ticket_id = result.get('id', None)
        if ticket_id:
            return {
                "success": True,
                "ticket_id": ticket_id,
                "message": f"✅ Ticket created successfully with ID #{ticket_id}\n\n🔗 View your ticket progress: https://nemakmxdev.haloitsm.com/ticket?id={ticket_id}&showmenu=true"
            }
        else:
            return {
                "success": True,
                "ticket_id": None,
                "message": "✅ Ticket created successfully!"
            }
    else:
        return {
            "success": False,
            "ticket_id": None,
            "message": f"❌ Failed to create ticket: {response.status_code} - {response.text}"
        }
