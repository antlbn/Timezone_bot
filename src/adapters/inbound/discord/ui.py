import discord
from discord import ui
from core.domain.enums import Platform

class TimezoneModal(ui.Modal, title="Timezone Setup"):
    city = ui.TextInput(label="City", placeholder="e.g. London, Tokyo")
    
    def __init__(self, onboarding_coordinator):
        super().__init__()
        self.onboarding_coordinator = onboarding_coordinator

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        res = await self.onboarding_coordinator.complete(
            user_id=interaction.user.id,
            city_raw=self.city.value,
            platform=Platform.DISCORD,
        )
        if res.ok:
            await interaction.followup.send(f"✅ Timezone set to **{res.timezone_name}** ({res.city} {res.flag})", ephemeral=True)
            try:
                if hasattr(self, 'origin_message') and self.origin_message:
                    await self.origin_message.delete()
            except Exception:
                pass
        else:
            await interaction.followup.send(f"❌ Could not resolve city: {self.city.value}", ephemeral=True)

class SetTimezoneView(ui.View):
    def __init__(self, target_user_id: int, onboarding_coordinator):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.onboarding_coordinator = onboarding_coordinator

    @ui.button(label="⚙️ Settings", style=discord.ButtonStyle.primary, custom_id="settz_button")
    async def start_setup(self, interaction: discord.Interaction, button: ui.Button):
        modal = TimezoneModal(self.onboarding_coordinator)
        modal.origin_message = interaction.message
        await interaction.response.send_modal(modal)

    @ui.button(label="🚫 Skip", style=discord.ButtonStyle.secondary, custom_id="skip_button")
    async def skip_setup(self, interaction: discord.Interaction, button: ui.Button):
        await self.onboarding_coordinator.decline(
            user_id=interaction.user.id,
            platform=Platform.DISCORD,
        )
        await interaction.response.send_message(
            "Got it! I won't bother you again. Use `/tb_settz` if you change your mind.", 
            ephemeral=True
        )
        try:
            if interaction.message:
                await interaction.message.delete()
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("❌ This button is not for you!", ephemeral=True)
            return False
        return True
