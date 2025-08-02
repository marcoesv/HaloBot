from botbuilder.core import ActivityHandler, TurnContext
from services.message_processor import process_message
from services.file_service import process_attachments

class HaloBot(ActivityHandler):
    def __init__(self, conversation_state):
        self.conversation_state = conversation_state
        self.state_accessor = self.conversation_state.create_property("TicketState")

    async def on_message_activity(self, turn_context: TurnContext):
        # Load or initialize conversation state dict
        state = await self.state_accessor.get(turn_context, dict)
        
        user_input = turn_context.activity.text.strip() if turn_context.activity.text else ""
        
        # Process any file attachments
        attachments_data = None
        if turn_context.activity.attachments:
            attachments_data = await process_attachments(turn_context.activity.attachments)
            if attachments_data and attachments_data.get("error"):
                # Send error message for invalid files
                await turn_context.send_activity(attachments_data["error"])
                await self.conversation_state.save_changes(turn_context)
                return

        # Pass user input, state, and attachments to processing function
        reply = await process_message(user_input, state, attachments_data)

        await turn_context.send_activity(reply)

        # Save changes to state
        await self.conversation_state.save_changes(turn_context)
