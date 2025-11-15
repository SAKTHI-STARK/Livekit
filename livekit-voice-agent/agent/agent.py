import os
import sys
import json
import traceback
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    AgentSession,
    Agent,
    RoomInputOptions,
    UserStateChangedEvent,
    function_tool,
    RunContext,
    get_job_context,
    metrics, 
    MetricsCollectedEvent,
)
from livekit.plugins import noise_cancellation, silero, elevenlabs, deepgram, google
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --- Local Imports ---
# from EnglishAgent import EnglishAssistant as EnglishAgent
# from HindiAgent import HindiAssistant as HindiAgent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from VariableHandler.DynamicVariableHandler import DynamicVariableHandler

# --- Load Environment Variables ---
load_dotenv(".env.local")


# AGENT DEFINITION
class GenericAgent(Agent):
    def __init__(self, instructions: str | None = None) -> None:
        super().__init__(instructions=instructions)

    # Language Switching Tools
    # @function_tool()
    # async def transfer_to_english(self, context: RunContext):
    #     return EnglishAgent(chat_ctx=self.chat_ctx), "Transferring to English."

    # @function_tool()
    # async def transfer_to_hindi(self, context: RunContext):
    #     return HindiAgent(chat_ctx=self.chat_ctx), "Transferring to Hindi."

    # Geolocation Tool
    @function_tool()
    async def sent_link(self, context: RunContext):
        try:
            room = get_job_context().room
            participant_identity = next(iter(room.remote_participants))

            response = await room.local_participant.perform_rpc(
                destination_identity=participant_identity,
                method="sent_link",
                payload="{}",
                response_timeout=10.0,
            )
            return response
        except Exception as e:
            print("Error retrieving user location:", e)
            raise Exception("Unable to retrieve user location.")

# ENTRYPOINT FUNCTION
async def entrypoint(ctx: agents.JobContext):
    usage_collector = metrics.UsageCollector()
    await ctx.connect()
    # Create the Agent Session
    session = AgentSession(
        stt=deepgram.STTv2(model="flux-general-en", eager_eot_threshold=0.4),
        llm=google.LLM(model="gemini-2.0-flash"),
        tts=elevenlabs.TTS(
            voice_id="ODq5zmih8GrVes37Dizd",
            model="eleven_multilingual_v2",
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    # Event Handlers
    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):
        if ev.new_state == "away":
            session.generate_reply(instructions="Hey, are you still there?")
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    # Shutdown logging (fixed: define function, then add callback outside body)
    async def log_usage():
        summary = usage_collector.get_summary()
        print(f"Usage: {summary}", flush=True)

    ctx.add_shutdown_callback(log_usage)
    try:
        participant = await ctx.wait_for_participant()
        user_name = participant.name if participant and participant.name else "there"
        attributes = participant.attributes or {}

        first_message = attributes.get("first message")
        system_prompt = attributes.get("system_prompt")

        # Use VariableHandler to load user data, populate variables, and resolve templates
        var_handler = DynamicVariableHandler()
        resolved_first_message, resolved_system_prompt = var_handler.load_and_resolve(
            user_name=user_name,
            first_message=first_message,
            system_prompt=system_prompt,
        )

        await session.start(
            room=ctx.room,
            agent=GenericAgent(instructions=resolved_system_prompt),
            room_input_options=RoomInputOptions(
                noise_cancellation=None  # Change to noise_cancellation.NoiseCancellation() if needed
            ),
        )

        await session.say(resolved_first_message)

    except Exception as e:
        print("Exception during session setup:", e)
        traceback.print_exc()

# MAIN EXECUTION
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
