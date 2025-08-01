from botbuilder.core import ActivityHandler, TurnContext
import halo_api

class HaloBot(ActivityHandler):
    def __init__(self, conversation_state):
        self.conversation_state = conversation_state
        self.state_accessor = self.conversation_state.create_property("TicketState")

    async def on_message_activity(self, turn_context: TurnContext):
        # Load or initialize conversation state dict
        state = await self.state_accessor.get(turn_context, dict)
        
        user_input = turn_context.activity.text.strip()

        # Pass user input and state to your existing processing function
        reply = await halo_api.process_message(user_input, state)

        await turn_context.send_activity(reply)

        # Save changes to state
        await self.conversation_state.save_changes(turn_context)
