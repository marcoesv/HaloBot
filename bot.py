import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# Estado global simple (para un solo usuario)
session_state = {
    "status": "esperando_instruccion",
    "conversation_history": [],
    "user_language": "auto"  # Auto-detect or set based on first interaction
}

def detect_intent_with_ai(user_message, current_status):
    """Use Gemini to intelligently detect user intent regardless of language"""
    
    intent_prompt = f"""You are an intent classifier for a support chatbot. Analyze the user's message and current conversation state, then respond with ONLY a JSON object.

Current conversation state: {current_status}

User message: "{user_message}"

Classify the intent into ONE of these categories:
- "create_ticket": User wants to create a support ticket, contact an agent, or escalate to human support
- "report_problem": User is describing a problem but hasn't explicitly asked for a ticket
- "confirm_yes": User is agreeing, confirming, or saying yes to a previous question
- "confirm_no": User is declining, rejecting, or saying no to a previous question
- "general_query": General questions, greetings, or other conversations
- "troubleshoot_continue": User wants to continue troubleshooting or providing more details

Consider the context and intent behind the message, not just specific keywords. Users might express the same intent in different languages or ways.

Respond ONLY with this JSON format:
{{"intent": "intent_name", "confidence": 0.95, "detected_language": "en/es/other"}}"""

    payload = {
        "contents": [
            {
                "role": "user", 
                "parts": [{"text": intent_prompt}]
            }
        ]
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            try:
                ai_response = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                # Clean the response and extract JSON
                ai_response = ai_response.strip()
                if ai_response.startswith('```json'):
                    ai_response = ai_response.replace('```json', '').replace('```', '').strip()
                
                intent_data = json.loads(ai_response)
                return intent_data.get("intent", "general_query"), intent_data.get("detected_language", "unknown")
            except (json.JSONDecodeError, KeyError, IndexError):
                # Fallback: simple keyword detection if AI parsing fails
                return fallback_intent_detection(user_message), "unknown"
        else:
            return fallback_intent_detection(user_message), "unknown"
            
    except Exception as e:
        return fallback_intent_detection(user_message), "unknown"

def fallback_intent_detection(message):
    """Simple fallback intent detection if AI fails"""
    text = message.lower()
    
    # Multi-language keywords for fallback
    ticket_words = ["ticket", "agent", "agente", "human", "humano", "support", "soporte", "help", "ayuda"]
    problem_words = ["problem", "problema", "error", "issue", "bug", "broken", "roto", "fail", "falla"]
    yes_words = ["yes", "sí", "si", "ok", "okay", "sure", "dale", "perfecto"]
    no_words = ["no", "nope", "cancel", "cancelar", "never mind"]
    
    if any(word in text for word in ticket_words):
        return "create_ticket"
    elif any(word in text for word in problem_words):
        return "report_problem"
    elif any(word in text for word in yes_words):
        return "confirm_yes"
    elif any(word in text for word in no_words):
        return "confirm_no"
    else:
        return "general_query"

def generate_contextual_response(user_message, intent, current_status, detected_language):
    """Generate a contextual response using Gemini based on intent and status"""
    
    # Determine response language preference
    lang_instruction = ""
    if detected_language == "es" or session_state["user_language"] == "es":
        lang_instruction = "Respond in Spanish."
        session_state["user_language"] = "es"
    elif detected_language == "en" or session_state["user_language"] == "en":
        lang_instruction = "Respond in English."
        session_state["user_language"] = "en"
    else:
        lang_instruction = "Respond in the same language as the user's message."
    
    context_prompt = f"""You are HaloBot, a professional support chatbot. {lang_instruction}

Current situation:
- User's intent: {intent}
- Current conversation state: {current_status}
- User message: "{user_message}"

Guidelines:
- Be helpful, professional, and concise
- Don't use asterisks for formatting
- If creating a ticket, mention "calling HALO POST API endpoint" at the beginning
- Match the user's language and tone
- Be supportive but not overly verbose

Provide an appropriate response based on the intent and current state."""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": context_prompt}]
            }
        ]
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            try:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                return "I apologize, but I'm having trouble processing your request right now. Could you please try again?"
        else:
            return "I'm experiencing some technical difficulties. Please try again in a moment."
            
    except Exception as e:
        return "Sorry, I'm having connection issues. Please try again."

def generate_bot_reply(user_message):
    """Main logic with AI-powered intent detection"""
    current_status = session_state["status"]
    
    # Use AI to detect intent
    intent, detected_language = detect_intent_with_ai(user_message, current_status)
    
    # Add message to conversation history
    session_state["conversation_history"].append(f"User: {user_message}")
    
    # State machine logic based on AI-detected intent
    if current_status == "esperando_instruccion":
        if intent == "create_ticket":
            session_state["status"] = "esperando_instruccion"
            reply = "calling HALO POST API endpoint\n" + generate_contextual_response(
                user_message, intent, "ticket_created", detected_language
            )
        
        elif intent == "report_problem":
            session_state["status"] = "en_troubleshoot" 
            reply = generate_contextual_response(
                user_message, intent, "starting_troubleshoot", detected_language
            )
        
        else:
            # General queries
            reply = generate_contextual_response(
                user_message, intent, "general_help", detected_language
            )
    
    elif current_status == "en_troubleshoot":
        if intent == "create_ticket":
            session_state["status"] = "esperando_instruccion"
            reply = "calling HALO POST API endpoint\n" + generate_contextual_response(
                user_message, intent, "ticket_created_from_troubleshoot", detected_language
            )
        
        elif intent == "confirm_yes":
            session_state["status"] = "esperando_confirmacion_ticket"
            reply = generate_contextual_response(
                user_message, "ask_ticket_confirmation", "asking_ticket_confirmation", detected_language
            )
        
        elif intent == "confirm_no":
            session_state["status"] = "esperando_instruccion"
            reply = generate_contextual_response(
                user_message, "continue_troubleshoot", "continue_helping", detected_language
            )
        
        else:
            # Continue troubleshooting
            reply = generate_contextual_response(
                user_message, intent, "continuing_troubleshoot", detected_language
            )
    
    elif current_status == "esperando_confirmacion_ticket":
        if intent in ["confirm_yes", "create_ticket"]:
            session_state["status"] = "esperando_instruccion"
            reply = "calling HALO POST API endpoint\n" + generate_contextual_response(
                user_message, "ticket_confirmed", "ticket_created_confirmed", detected_language
            )
        
        elif intent == "confirm_no":
            session_state["status"] = "esperando_instruccion"
            reply = generate_contextual_response(
                user_message, "ticket_declined", "ticket_declined", detected_language
            )
        
        else:
            reply = generate_contextual_response(
                user_message, "clarify_ticket_decision", "need_ticket_clarification", detected_language
            )
    
    else:
        # Reset to initial state if something goes wrong
        session_state["status"] = "esperando_instruccion"
        reply = generate_contextual_response(
            "Hello", "greeting", "reset_greeting", detected_language
        )
    
    # Add bot reply to conversation history
    session_state["conversation_history"].append(f"HaloBot: {reply}")
    
    return reply

def reset_session():
    """Reset the session state"""
    session_state["status"] = "esperando_instruccion"
    session_state["conversation_history"] = []
    session_state["user_language"] = "auto"

def get_conversation_summary():
    """Get a summary of the current conversation"""
    return "\n".join(session_state["conversation_history"][-10:])

# Run interactive chat if script is executed directly
if __name__ == "__main__":
    print("🤖 HaloBot is ready! (AI-powered intent detection)")
    print("Type 'exit' to quit, 'reset' to restart, or 'history' to see conversation.\n")
    
    while True:
        try:
            user_input = input("You: ")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")
            break

        if user_input.strip().lower() in ["exit", "quit"]:
            print("👋 Goodbye!")
            break
        
        elif user_input.strip().lower() == "reset":
            reset_session()
            print("🔄 Session reset!\n")
            continue
            
        elif user_input.strip().lower() == "history":
            print("\n📝 Conversation History:")
            print(get_conversation_summary())
            print()
            continue

        reply = generate_bot_reply(user_input)
        print(f"HaloBot: {reply}\n")