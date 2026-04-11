from src.core.domain.commands import Command, SendReply, SavePending, ShowOnboarding, NoOp
from src.core.domain.value_objects import MessageContext, PendingMessage

def create_commands(ctx: MessageContext) -> list[Command]:
    if not ctx.detection or not ctx.detection.time_mentioned:
        return [NoOp()]

    if ctx.input.sender is not None and ctx.input.sender.timezone:
        if ctx.reply_text:
            return [SendReply(text=ctx.reply_text)]
        return [NoOp()]

    if ctx.input.sender is None or not ctx.input.sender.onboarding_declined:
        pending = PendingMessage(
            text=ctx.input.text,
            author_name=ctx.input.author_name,
            chat_id=ctx.input.chat_id,
            timestamp_utc=ctx.input.timestamp_utc,
        )
        return [
            SavePending(user_id=ctx.input.user_id, platform=ctx.input.platform, message=pending),
            ShowOnboarding(user_id=ctx.input.user_id, author_name=ctx.input.author_name, chat_id=ctx.input.chat_id)
        ]

    return [NoOp()]
