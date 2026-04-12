import discord
from discord import ui

class SetTimezoneView(ui.View):
    def __init__(self, target_user_id: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @ui.button(label="⚙️ Settings", style=discord.ButtonStyle.primary, custom_id="settz_button")
    async def start_setup(self, interaction: discord.Interaction, button: ui.Button):
        # For M2.5 Slice, we just tell them to use the slash command to simplify
        # A full modal takes more boilerplate, but meets slice criteria
        await interaction.response.send_message("Please use the `/tb_settz` command to set your timezone!", ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("❌ This button is not for you!", ephemeral=True)
            return False
        return True
