from dotenv import load_dotenv
load_dotenv(".env.local")
import json
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, UserStateChangedEvent, function_tool, RunContext
from agent.EnglishAgent import EnglishAssistant as EnglishAgent
from agent.HindiAgent import HindiAssistant as HindiAgent
from livekit.plugins import noise_cancellation, silero, elevenlabs
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import prompts.Languageswitch as LS

class LanChooseAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=LS.instruction_choose_language)

    @function_tool()
    async def transfer_to_english(self, context: RunContext):
        return EnglishAgent(chat_ctx=self.chat_ctx), "Transferring to English"

    @function_tool()
    async def transfer_to_hindi(self, context: RunContext):
        return HindiAgent(chat_ctx=self.chat_ctx), "Transferring to Hindi"


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt="deepgram/nova-2-general",
        llm="openai/gpt-4.1-mini",
        tts=elevenlabs.TTS(
            voice_id="ODq5zmih8GrVes37Dizd",
            model="eleven_multilingual_v2"
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=LanChooseAgent(),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    try:
        participant = await ctx.wait_for_participant()
        user_name = None
        if participant and getattr(participant, "metadata", None):
            try:
                md = json.loads(participant.metadata)
                user_name = md.get("name") or md.get("username") or md.get("user_name")
            except Exception:
                user_name = participant.metadata

        if not user_name:
            user_name = getattr(participant, "identity", None) or "there"
        await session.say(f"Hello {user_name}! This is Nova from Discovery Insurance. To assist you better, could you please let me know your preferred language for this conversation? We offer support in both English and Hindi.")

    except Exception:
        pass

    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):  
        if ev.new_state == 'away':
             session.generate_reply(instructions="Please check with the user if user is still with us like e.g.'Please let me know if you’re still with us' or 'Hey, are you still there?' after that wait for user response then proceed further")

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
