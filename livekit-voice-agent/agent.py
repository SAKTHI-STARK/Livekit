import os
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

def load_user_data(file_path="user_data.json"):
    if not os.path.exists(file_path):
        print(f"JSON metadata file missing: {file_path}")
        return {}

    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print("Error loading metadata JSON:", e)
        return {}


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

    # Session Initialization
    try:
        participant = await ctx.wait_for_participant()
        user_name = participant.name if participant and participant.name else "there"
        attributes = participant.attributes or {}

        all_user_details = load_user_data()
        user_data = all_user_details.get(user_name,{})

        expiry_data = user_data.get("expiry_date")
        date_of_birth = user_data.get("date_of_birth")
        policy_number = user_data.get("policy_number")
        monthly_premium_amt = user_data.get("monthly_premium_amt")
        excess_amt = user_data.get("excess_amt")
        
        first_message = attributes.get("first message")
        system_prompt = attributes.get("system_prompt")

        await session.start(
            room=ctx.room,
            agent=GenericAgent(instructions=system_prompt.format(expiry_data=expiry_data,date_of_birth=date_of_birth,policy_number=policy_number,monthly_premium_amt=monthly_premium_amt,excess_amt=excess_amt)),
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
