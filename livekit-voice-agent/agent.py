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
)
from livekit.plugins import noise_cancellation, silero, elevenlabs, deepgram, google
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --- Local Imports ---
from agent.EnglishAgent import EnglishAssistant as EnglishAgent
from agent.HindiAgent import HindiAssistant as HindiAgent
from rag_engine import query_info

# --- Load Environment Variables ---
load_dotenv(".env.local")


# AGENT DEFINITION
class GenericAgent(Agent):
    def __init__(self, instructions: str | None = None) -> None:
        super().__init__(instructions=instructions)

    # Language Switching Tools
    @function_tool()
    async def transfer_to_english(self, context: RunContext):
        return EnglishAgent(chat_ctx=self.chat_ctx), "Transferring to English."

    @function_tool()
    async def transfer_to_hindi(self, context: RunContext):
        return HindiAgent(chat_ctx=self.chat_ctx), "Transferring to Hindi."

    # RAG Query Tool
    @function_tool()
    async def query_info_tool(self, query: str) -> str:
        try:
            result = await query_info(query)
            # print("RAG query result:", result)
            return result
        except Exception as e:
            print("Error in RAG query:", e)
            return "Sorry, I couldn't fetch the information right now."

    # Geolocation Tool
    @function_tool()
    async def get_user_location(self, context: RunContext, high_accuracy: bool):
        try:
            room = get_job_context().room
            participant_identity = next(iter(room.remote_participants))

            response = await room.local_participant.perform_rpc(
                destination_identity=participant_identity,
                method="getUserLocation",
                payload=json.dumps({"highAccuracy": high_accuracy}),
                response_timeout=10.0 if high_accuracy else 5.0,
            )
            return response
        except Exception as e:
            print("Error retrieving user location:", e)
            raise Exception("Unable to retrieve user location.")

# ENTRYPOINT FUNCTION
async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint for the LiveKit agent."""
    await ctx.connect()
    print("Connected to LiveKit room.")

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

    # Session Initialization
    try:
        participant = await ctx.wait_for_participant()
        user_name = participant.name if participant and participant.name else "there"
        attributes = participant.attributes or {}

        first_message = attributes.get("first message", "Hello {user_name}")
        system_prompt = attributes.get("system_prompt")

        await session.start(
            room=ctx.room,
            agent=GenericAgent(instructions=system_prompt),
            room_input_options=RoomInputOptions(
                noise_cancellation=None  # Change to noise_cancellation.NoiseCancellation() if needed
            ),
        )

        await session.say(first_message.format(user_name=user_name))

    except Exception as e:
        print("Exception during session setup:", e)
        traceback.print_exc()

    # Shutdown Sequence
    await ctx.wait_for_disconnect()
    await ctx.shutdown()
    print("Shutdown complete.")

# MAIN EXECUTION
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
