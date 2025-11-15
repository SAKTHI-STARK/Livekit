from livekit.agents import Agent, function_tool, RunContext
from ..prompts import InsurenceExpireHindi as IPromptsHindi
class HindiAssistant(Agent):
    def __init__(self,chat_ctx=None) -> None:
        super().__init__(
            instructions=IPromptsHindi.instruction_discovery_expiring_policy_hindi_prompt,
        )
        chat_ctx = chat_ctx
            
    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions=IPromptsHindi.first_msg)
