# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import logging
from typing import List
from botbuilder.core import (
    ConversationState,
    UserState,
    TurnContext,
    MessageFactory,
)
from botbuilder.dialogs import Dialog
from botbuilder.schema import ChannelAccount, ActivityTypes, InvokeResponse

from helpers.dialog_helper import DialogHelper
from .dialog_bot import DialogBot


class AuthBot(DialogBot):
    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        dialog: Dialog,
    ):
        super(AuthBot, self).__init__(conversation_state, user_state, dialog)
        self.logger = logging.getLogger(__name__)

    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            # Greet anyone that was not the target (recipient) of this message.
            # To learn more about Adaptive Cards, see https://aka.ms/msbot-adaptivecards for more details.
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Welcome to AuthenticationBot. Type anything to get logged in. Type "
                    "'logout' to sign-out."
                )

    async def on_token_response_event(self, turn_context: TurnContext):
        # Run the Dialog with the new Token Response Event Activity.
        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )

    async def on_teams_signin_verify_state(self, turn_context: TurnContext):
        # Run the Dialog with the new Token Response Event Activity.
        # The OAuth Prompt needs to see the Invoke Activity in order to complete the login process.
        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )

    async def on_invoke_activity(self, turn_context: TurnContext) -> InvokeResponse:
        """Handle invoke activities including feedback submissions"""
        try:
            if turn_context.activity.name == "message/submitAction":
                # Handle feedback submission
                await self._handle_feedback_submission(turn_context)
                # Don't manually create invoke response - let the SDK handle it
                # This was the main issue in GitHub issue #2510
                return None
            elif turn_context.activity.name == "message/fetchTask":
                # Handle custom feedback form fetch (if using custom feedback)
                return await self._handle_fetch_feedback_task(turn_context)
            else:
                # Handle other invoke activities (like signin verification)
                return await super().on_invoke_activity(turn_context)
        except Exception as e:
            self.logger.error(f"Error in on_invoke_activity: {e}")
            # Don't return error responses - let the SDK handle error scenarios
            return None

    async def on_message_activity(self, turn_context: TurnContext):
        # Run the normal dialog flow for message activities
        await super().on_message_activity(turn_context)
    
    async def _handle_fetch_feedback_task(self, turn_context: TurnContext) -> InvokeResponse:
        """Handle fetch task for custom feedback form (if using custom feedback)"""
        # This would be called if feedbackLoop.type was set to "custom"
        # For now, we're using the default feedback form, so this won't be called
        # Return None to let the SDK handle the default response
        return None
    
    async def _handle_feedback_submission(self, turn_context: TurnContext):
        """Handle feedback submission from Teams feedback buttons"""
        try:
            feedback_data = turn_context.activity.value
            action_name = feedback_data.get("actionName")
            action_value = feedback_data.get("actionValue", {})
            
            if action_name == "feedback":
                reaction = action_value.get("reaction")  # "like" or "dislike"
                feedback_text = action_value.get("feedback", "")
                
                # Parse feedback text if it's JSON
                if feedback_text:
                    try:
                        feedback_json = json.loads(feedback_text)
                        feedback_text = feedback_json.get("feedbackText", feedback_text)
                    except json.JSONDecodeError:
                        pass  # Keep original text if not JSON
                
                # Log the feedback
                self.logger.info("=== Teams Feedback Received ===")
                self.logger.info(f"User: {turn_context.activity.from_property.name if turn_context.activity.from_property else 'Unknown'}")
                self.logger.info(f"User ID: {turn_context.activity.from_property.id if turn_context.activity.from_property else 'Unknown'}")
                self.logger.info(f"Reaction: {reaction}")
                self.logger.info(f"Feedback Text: {feedback_text}")
                self.logger.info(f"Activity ID: {turn_context.activity.reply_to_id}")
                self.logger.info("=== End Teams Feedback ===")
                
                # IMPORTANT: Don't send any activities here for feedback
                # The SDK handles the invoke response automatically
                # Sending activities can cause the serialization errors mentioned in issue #2510
                
        except Exception as e:
            self.logger.error(f"Error processing Teams feedback: {e}")

