from livekit.agents import Agent
from prompts import InsurenceExpire as IPrompts

class EnglishAssistant(Agent):
    def __init__(self,chat_ctx=None) -> None:
        super().__init__(
            instructions=IPrompts.instructions,
        )
        chat_ctx = chat_ctx
        
    async def on_enter(self) -> None:
        await self.session.say(IPrompts.first_msg)

    