from dotenv import load_dotenv
load_dotenv(".env.local")
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, UserStateChangedEvent, function_tool, RunContext
from agent.EnglishAgent import EnglishAssistant as EnglishAgent
from agent.HindiAgent import HindiAssistant as HindiAgent
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import sys
import prompts.Languageswitch as LS

class LanChooseAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=LS.instruction_choose_language,
        )
        
    async def on_enter(self) -> None:
        await self.session.say(LS.first_msg)

    @function_tool()
    async def transfer_to_english(self, context: RunContext):
        return EnglishAgent(chat_ctx=self.chat_ctx), "Transferring to english"
    
    @function_tool()
    async def transfer_to_hindi(self, context: RunContext):
        return HindiAgent(chat_ctx=self.chat_ctx), "Transferring to hindi"


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt="deepgram/nova-2-general",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
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
    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):
        # print(f"User state change from {ev.old_state} to {ev.new_state}")
        if ev.new_state == 'away':
            session.say("Please let me know if you’re still with us")

    # @session.on("agent_state_changed")
    # def on_agent_state_changed(ev: AgentStateChangedEvent):
    #     print(f"Agent state change from {ev.old_state} to {ev.new_state}")

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))