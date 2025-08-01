import os
from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapterSettings, BotFrameworkAdapter,
    ConversationState, MemoryStorage
)
from botbuilder.schema import Activity

from halo_bot import HaloBot

APP_ID = os.getenv("MicrosoftAppId", "")
APP_PASSWORD = os.getenv("MicrosoftAppPassword", "")

adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
adapter = BotFrameworkAdapter(adapter_settings)

memory = MemoryStorage()
conversation_state = ConversationState(memory)

bot = HaloBot(conversation_state)

async def messages(req):
    if "application/json" in req.headers.get("Content-Type", ""):
        body = await req.json()
    else:
        return web.Response(status=415)
    
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")
    
    response = await adapter.process_activity(activity, auth_header, bot.on_turn)
    if response:
        return web.json_response(data=response.body, status=response.status)
    return web.Response(status=200)

app = web.Application()
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    web.run_app(app, host="localhost", port=3978)
