from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    AgentSession,
    Agent,
    RoomInputOptions,
    UserStateChangedEvent,
    function_tool,
    RunContext,
)
from agent.EnglishAgent import EnglishAssistant as EnglishAgent
from agent.HindiAgent import HindiAssistant as HindiAgent
from livekit.plugins import noise_cancellation, silero, elevenlabs, deepgram, google
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import prompts.Languageswitch as LS
load_dotenv(".env.local")

class LanChooseAgent(Agent):
    def __init__(self, instructions=None) -> None:
        super().__init__(instructions=instructions)

    @function_tool()
    async def transfer_to_english(self, context: RunContext):
        return EnglishAgent(chat_ctx=self.chat_ctx), "Transferring to English"

    @function_tool()
    async def transfer_to_hindi(self, context: RunContext):
        return HindiAgent(chat_ctx=self.chat_ctx), "Transferring to Hindi"


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    print("Connected to LiveKit room")

    session = AgentSession(
        stt=deepgram.STTv2(
            model="flux-general-en",
            eager_eot_threshold=0.4,
        ),
        llm=google.LLM(model="gemini-2.0-flash"),
        tts=elevenlabs.TTS(
            voice_id="ODq5zmih8GrVes37Dizd",
            model="eleven_multilingual_v2",
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    try:
        participant = await ctx.wait_for_participant()
        user_name = participant.name if participant and participant.name else "there"
        attributes = participant.attributes or {}
        first_message = attributes.get("first message", "Hello {user_name}")
        system_prompt = attributes.get("system_prompt")

        await session.start(
            room=ctx.room,
            agent=LanChooseAgent(instructions=system_prompt),
            room_input_options=RoomInputOptions(
                noise_cancellation=None  # or noise_cancellation.BVC()
            ),
        )

        await session.say(first_message.format(user_name=user_name))

    except Exception as e:
        print(f" Exception: {e}")

    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):
        if ev.new_state == "away":
            session.generate_reply(
                instructions="Please check with the user if they are still here, e.g. 'Hey, are you still there?'"
            )
    await ctx.wait_for_disconnect()
    await ctx.shutdown()
    print("Shutdown complete")


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
