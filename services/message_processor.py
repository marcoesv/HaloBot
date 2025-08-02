from services.halo_service import get_halo_token, send_ticket_to_halo
from services.openai_service import call_openai
from services.file_service import add_attachments_to_details_html
from utils.json_parser import extract_json_from_reply

def is_confirmation(user_input):
    """Check if user input is a confirmation or rejection"""
    confirmation_words = ['yes', 'y', 'ok', 'okay', 'confirm', 'submit', 'send', 'create']
    rejection_words = ['no', 'n', 'cancel', 'abort', 'stop']
    
    user_lower = user_input.lower().strip()
    
    if any(word in user_lower for word in confirmation_words):
        return True
    elif any(word in user_lower for word in rejection_words):
        return False
    else:
        return None

def get_system_prompt():
    """Get the system prompt for OpenAI"""
    return """
You are a helpful IT support assistant that creates tickets in a conversational, human-like manner. Always respond in the user's input language.

Your goal is to gather information naturally through conversation, not by overwhelming users with requirements.

Conversation Flow:
1. When users first mention needing help/creating a ticket, respond warmly and ask them to describe their issue
2. Once you understand the problem, ask for their name and email if not provided
3. Based on their description, intelligently determine the appropriate impact and urgency
4. Classify as Incident (fixing problems) or Request (new services/access)
5. Create a summary for confirmation

Ticket Types:
- Incident (tickettype_id: 1): Fix problems (outages, errors, broken functionality)  
- Request (tickettype_id: 3): New services (access, software, setup)

Impact Assessment (choose intelligently based on user's description):
- Global/VIP (1): Affects many users, executives, or critical systems
- Regional (2): Affects a region, team, or department  
- Plant/Department (3): Affects a specific plant or department
- Individual User (4): Affects only the requesting user

Urgency Assessment (choose intelligently based on user's description):
- Unable to work (1): User completely blocked, critical system down
- Workaround exists (2): User can work but with difficulty
- Interferes with work (3): User can work but it's inconvenient
- Would assist work (4): Nice to have, not blocking work

File Attachment Handling:
- When users attach screenshots/images, acknowledge them naturally and CONTINUE the conversation flow
- If you already have enough information to create a ticket (name, email, issue description), proceed to create the ticket summary after acknowledging the image
- Don't just acknowledge - use the file attachment as a signal to move forward if ready
- Say things like "Thanks for the screenshot! Now let me create your ticket..." and then proceed
- Screenshots help visualize technical issues and will be embedded in the ticket
- For documents (PDFs, Word docs, etc.), ask users to upload them to OneDrive and share the link
- Always maintain conversation momentum - file attachments should enhance, not stall the conversation

When you have gathered all information naturally, respond with:
1. A conversational summary like: "Let me summarize your request to make sure I have everything right..."

📋 Ticket Summary
Type: [Incident/Request]
Title: [summary]
User: [Full Name] ([email@company.com])
Description: [details without HTML tags]
Impact: [Global/VIP, Regional, Plant/Department, Individual User] 
Urgency: [Unable to work, Workaround exists, Interferes with work, Would assist work]
Attachments: [If files were attached, mention them here]

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

IMPORTANT: Always include a user information table at the TOP of details_html:
<table border="1" style="border-collapse: collapse; margin-bottom: 20px; width: 100%; max-width: 800px;">
<tr><td style="width: 150px; vertical-align: top; background-color: #f5f5f5;"><strong>Name:</strong></td><td style="padding: 8px;">[Full Name]</td></tr>
<tr><td style="width: 150px; vertical-align: top; background-color: #f5f5f5;"><strong>Email:</strong></td><td style="padding: 8px;">[email@nemak.com]</td></tr>
<tr><td style="width: 150px; vertical-align: top; background-color: #f5f5f5;"><strong>Issue Description:</strong></td><td style="padding: 8px; word-wrap: break-word;">[Brief description of the problem/request]</td></tr>
</table>

Conversation Guidelines:
- Be conversational and friendly, not robotic
- Ask one thing at a time, don't overwhelm users
- Use your intelligence to determine impact/urgency from their description
- Guide the conversation naturally
- If users seem unsure about technical details, ask follow-up questions
- When users attach files and you have enough info (name, email, issue), acknowledge the file and CREATE THE TICKET
- Don't wait for additional prompts - file attachments often signal "I'm ready to submit"
- For anything not IT-related, respond: "I cannot help with that."
"""

async def process_message(user_input, state, attachments_data=None):
    """Main message processing function"""
    if "halo_token" not in state:
        token = get_halo_token()
        state["halo_token"] = token
    
    if state.get("awaiting_confirmation"):
        confirmation = is_confirmation(user_input)
        if confirmation is True:
            ticket = state.get("pending_ticket")
            if ticket:
                # Send ticket to Halo
                result = send_ticket_to_halo(ticket, state["halo_token"])
                
                if result["success"]:
                    state.clear()
                    return f"🎫 Your ticket has been submitted to the IT support team!\n\n{result['message']}"
                else:
                    state.clear()
                    return result["message"]
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
        # Initialize conversation messages with system prompt
        state["conversation"] = [{
            "role": "system",
            "content": get_system_prompt()
        }]

    # Handle file attachments
    if attachments_data and attachments_data.get("files"):
        file_count = len(attachments_data["files"])
        file_names = [f["filename"] for f in attachments_data["files"]]
        
        # Store attachments in state for later use
        state["pending_attachments"] = attachments_data
        
        # If user only sent files without text, add file context as a user message
        if not user_input.strip():
            user_message = f"[User attached {file_count} file(s): {', '.join(file_names)}]"
        else:
            # If user sent text with files, add file context to the message
            user_message = user_input + f"\n\n[User attached {file_count} file(s): {', '.join(file_names)}]"
    else:
        user_message = user_input

    # Only add to conversation if there's actual user input
    if user_message.strip():
        state["conversation"].append({"role": "user", "content": user_message})
        
        # Get AI response
        reply = await call_openai(state["conversation"])
        
        # Add AI response to conversation history
        if reply:
            state["conversation"].append({"role": "assistant", "content": reply})
    else:
        # File-only message was already handled above, this shouldn't be reached
        return "Thanks for the additional information!"

    if reply and "READY_TO_CREATE_TICKET" in reply:
        ticket_json = extract_json_from_reply(reply)
        if ticket_json:
            ticket = ticket_json[0]
            
            # Add attachments to the ticket's details_html if present
            if state.get("pending_attachments"):
                ticket["details_html"] = add_attachments_to_details_html(
                    ticket["details_html"], 
                    state["pending_attachments"]
                )
            
            state["pending_ticket"] = ticket
            state["awaiting_confirmation"] = True
            # Return the user-friendly part only
            parts = reply.split("READY_TO_CREATE_TICKET")
            return parts[0].strip() + "\n\n🔄 Does this look correct? Please reply 'yes' to submit or 'no' to cancel."
    elif reply:
        return reply
    else:
        return "Sorry, I didn't understand that. Could you please rephrase?"
