import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# Estado global simple (para un solo usuario)
session_state = {
    "status": "esperando_instruccion"
}

def interpret_intent(message):
    text = message.lower()
    if any(kw in text for kw in ["quiero levantar ticket", "abrir ticket", "necesito un agente", "hablar con alguien", "levantar ticket"]):
        return "levantar_ticket"
    elif any(kw in text for kw in ["no funciona", "problema", "error", "se cierra", "falla"]):
        return "troubleshoot"
    elif any(kw in text for kw in ["no quiero", "ya no", "cancelar", "ayuda de agente"]):
        return "confirmar_ticket"
    else:
        return "consulta_general"

def query_gemini(user_message):
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": """ou are HaloBot, a support agent. Respond professionally and helpfully in the user's language.
If the user wants to create a support ticket, reply with 'calling HALO POST API endpoint' and a message confirming the creation.
If the user needs troubleshooting help, offer suggestions before creating a ticket.
Do NOT create tickets by mistake.
Avoid using asterisks in any text formatting.
Keep your replies concise and direct."""
                    }
                ]
            },
            {
                "role": "user",
                "parts": [
                    {
                        "text": user_message
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(GEMINI_URL, headers=headers, json=payload)

    if response.status_code == 200:
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return "⚠️ Gemini gave an unexpected response format."
    else:
        return f"❌ Error: {response.status_code} - {response.text}"

def generate_bot_reply(user_message):
    intent = interpret_intent(user_message)
    status = session_state["status"]

    if status == "esperando_instruccion":
        if intent == "levantar_ticket":
            session_state["status"] = "esperando_confirmacion_ticket"
            return "*calling HALO POST API endpoint*\nGracias por tu mensaje, he abierto un ticket para ti. Un agente se pondrá en contacto contigo pronto. ¿Quieres agregar más detalles?"
        elif intent == "troubleshoot":
            session_state["status"] = "en_troubleshoot"
            return ("Entiendo que tienes un problema.")
        else:
            # Para consultas generales o desconocidas, consulta a Gemini para respuesta más natural
            return query_gemini(user_message)

    elif status == "en_troubleshoot":
        if intent == "confirmar_ticket":
            session_state["status"] = "esperando_confirmacion_ticket"
            return "¿Quieres que cree un ticket para que un agente revise el problema?"
        else:
            # Usa Gemini para continuar el troubleshooting de forma natural
            return query_gemini(user_message)

    elif status == "esperando_confirmacion_ticket":
        if intent in ["levantar_ticket", "confirmar_ticket"]:
            session_state["status"] = "esperando_instruccion"
            return "*calling HALO POST API endpoint*\nTicket creado."
        else:
            return "No he entendido si quieres crear el ticket. Por favor, dime si deseas que lo haga."

    else:
        session_state["status"] = "esperando_instruccion"
        return "Estoy aquí para ayudarte con soporte. ¿En qué puedo ayudarte?"

# Run interactive chat if script is executed directly
if __name__ == "__main__":
    print("🤖 HaloBot is ready! Type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("You: ")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")
            break

        if user_input.strip().lower() in ["exit", "quit"]:
            print("👋 Goodbye!")
            break

        reply = generate_bot_reply(user_input)
        print(f"HaloBot: {reply}\n")