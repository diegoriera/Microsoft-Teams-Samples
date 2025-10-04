# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
import logging
from datetime import datetime
from http import HTTPStatus

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    ConversationState,
    MemoryStorage,
    TurnContext,
    UserState,
)
from botbuilder.core.teams import (
    TeamsSSOTokenExchangeMiddleware
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.schema import Activity, ActivityTypes

from bots import AuthBot

# Create the loop and Flask app
from config import DefaultConfig
from dialogs import MainDialog

# Import and enable HTTP logging
from simple_http_logger import enable_http_logging

CONFIG = DefaultConfig()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable HTTP request/response logging for all outgoing HTTP calls
enable_http_logging()

# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(CONFIG))

# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Log the error with more context
    logger.error(f"Bot error in activity {context.activity.type}: {error}")
    logger.error(f"Activity name: {getattr(context.activity, 'name', 'N/A')}")
    
    # Don't send error messages for invoke activities to prevent serialization issues
    # This addresses the issue mentioned in GitHub issue #2510
    if context.activity.type == ActivityTypes.invoke:
        logger.warning("Error occurred during invoke activity - not sending user-facing error message")
        return
    
    # Send a message to the user only for non-invoke activities
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )

    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)


ADAPTER.on_turn_error = on_error

# Create MemoryStorage and state
MEMORY = MemoryStorage()
USER_STATE = UserState(MEMORY)
CONVERSATION_STATE = ConversationState(MEMORY)

ADAPTER.use(TeamsSSOTokenExchangeMiddleware(MEMORY, CONFIG.CONNECTION_NAME))

# Create dialog
DIALOG = MainDialog(CONFIG.CONNECTION_NAME)

# Create Bot
BOT = AuthBot(CONVERSATION_STATE, USER_STATE, DIALOG)


# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    try:
        # Parse the request body to extract the activity
        body = await req.text()
        if body:
            import json
            activity_data = json.loads(body)
            
            # Log conversation ID and related information
            conversation = activity_data.get('conversation', {})
            conversation_id = conversation.get('id', 'Unknown')
            conversation_name = conversation.get('name', 'N/A')
            
            # Log user information
            from_user = activity_data.get('from', {})
            user_id = from_user.get('id', 'Unknown')
            user_name = from_user.get('name', 'N/A')
            
            # Log channel and activity information
            channel_id = activity_data.get('channelId', 'Unknown')
            activity_type = activity_data.get('type', 'Unknown')
            activity_id = activity_data.get('id', 'Unknown')
            
            logger.info("=== Bot Activity Information ===")
            logger.info(f"Conversation ID: {conversation_id}")
            logger.info(f"Conversation Name: {conversation_name}")
            logger.info(f"Activity ID: {activity_id}")
            logger.info(f"Activity Type: {activity_type}")
            logger.info(f"Channel ID: {channel_id}")
            logger.info(f"User ID: {user_id}")
            logger.info(f"User Name: {user_name}")
            logger.info("=== End Activity Information ===")
            
    except Exception as e:
        logger.warning(f"Failed to parse activity for logging: {e}")
    
    return await ADAPTER.process(req, BOT)

APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        web.run_app(APP, host="localhost", port=CONFIG.PORT)
    except Exception as error:
        raise error
