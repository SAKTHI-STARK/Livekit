from livekit.agents import Agent
from prompts import InsurenceExpireHindi as IPromptsHindi
class HindiAssistant(Agent):
    def __init__(self,chat_ctx=None) -> None:
        super().__init__(
            instructions=IPromptsHindi.instructions_hindi,
        )
        chat_ctx = chat_ctx
        
    async def on_enter(self) -> None:
        await self.session.say(IPromptsHindi.first_msg_hindi)
