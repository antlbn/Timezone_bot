import discord
from discord import ui
import logging
from core.domain.enums import Platform
from core.services.onboarding import OnboardingCompletionUseCase
from adapters.inbound.discord.ui import texts

logger = logging.getLogger(__name__)

class TimezoneModal(ui.Modal, title="Timezone Setup"):
    city_input = ui.TextInput(
        label="City", 
        placeholder="e.g. London, Tokyo",
        min_length=2,
        max_length=100
    )
    
    def __init__(self, onboarding_completion: OnboardingCompletionUseCase):
        super().__init__()
        self.onboarding_completion = onboarding_completion
        self.origin_message = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        city_raw = self.city_input.value.strip()
        res = await self.onboarding_completion.complete(
            user_id=interaction.user.id,
            city_raw=city_raw,
            platform=Platform.DISCORD,
            author_name=interaction.user.display_name
        )
        
        if res.ok:
            await interaction.followup.send(
                texts.get_completion_text(res.timezone_name, res.city, res.flag), 
                ephemeral=True
            )
            if self.origin_message:
                try:
                    await self.origin_message.delete()
                except discord.HTTPException as e:
                    logger.debug(f"Failed to delete origin message: {e}")
        else:
            await interaction.followup.send(
                texts.get_city_not_found_text(city_raw), 
                ephemeral=True
            )


class SetTimezoneView(ui.View):
    def __init__(self, target_user_id: int, onboarding_completion: OnboardingCompletionUseCase):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.onboarding_completion = onboarding_completion

    @ui.button(label="⚙️ Settings", style=discord.ButtonStyle.primary, custom_id="settz_button")
    async def start_setup(self, interaction: discord.Interaction, button: ui.Button):
        modal = TimezoneModal(self.onboarding_completion)
        modal.origin_message = interaction.message
        await interaction.response.send_modal(modal)

    @ui.button(label="🚫 Skip", style=discord.ButtonStyle.secondary, custom_id="skip_button")
    async def skip_setup(self, interaction: discord.Interaction, button: ui.Button):
        await self.onboarding_completion.decline(
            user_id=interaction.user.id,
            platform=Platform.DISCORD,
        )
        await interaction.response.send_message(
            texts.get_decline_confirmation_text(), 
            ephemeral=True
        )
        if interaction.message:
            try:
                await interaction.message.delete()
            except discord.HTTPException as e:
                logger.debug(f"Failed to delete prompt message: {e}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message(
                texts.get_not_your_button_text(), 
                ephemeral=True
            )
            return False
        return True
