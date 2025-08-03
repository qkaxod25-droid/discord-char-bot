import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
from .ui_elements import SaveProfileView

class ProfileManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_file = os.path.join("data", "profiles.db")
        # 봇이 재시작되어도 View가 작동하도록 등록
        if not bot.persistent_views_added:
            bot.add_view(SaveProfileView())
            bot.persistent_views_added = True

    worldview_group = app_commands.Group(name="worldview", description="세계관 프리셋을 관리합니다.")

    @worldview_group.command(name="edit", description="기존 세계관의 설명을 수정합니다.")
    @app_commands.describe(name="수정할 세계관 이름", description="새로운 세계관 설명")
    async def worldview_edit(self, interaction: discord.Interaction, name: str, description: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("UPDATE worldviews SET description = ? WHERE name = ?", (description, name))
        if cursor.rowcount > 0:
            conn.commit()
            await interaction.response.send_message(f"'{name}' 세계관의 설명이 수정되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message(f"'{name}' 세계관을 찾을 수 없습니다.", ephemeral=True)
        conn.close()

    @worldview_group.command(name="list", description="저장된 모든 세계관의 목록과 설명을 보여줍니다.")
    async def worldview_list(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name, description FROM worldviews ORDER BY id")
        worldviews = cursor.fetchall()
        conn.close()
        if not worldviews:
            await interaction.response.send_message("저장된 세계관이 없습니다.", ephemeral=True)
            return
        embed = discord.Embed(title="🌌 세계관 목록", color=discord.Color.purple())
        for name, desc in worldviews:
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="profiles", description="내가 저장한 모든 캐릭터 프로필 목록을 봅니다.")
    async def list_profiles(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT character_name, worldview_name FROM profiles WHERE user_id = ? ORDER BY id", (interaction.user.id,))
        profiles = cursor.fetchall()
        conn.close()
        if not profiles:
            await interaction.response.send_message("저장된 프로필이 없습니다. `/generate`로 프로필을 만들고 저장해보세요.", ephemeral=True)
            return
        embed = discord.Embed(title=f"👤 {interaction.user.display_name}님의 프로필 목록", color=discord.Color.blue())
        description = ""
        for name, worldview in profiles:
            description += f"**{name}** (세계관: {worldview})\n"
        embed.description = description
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="load", description="저장된 캐릭터 프로필을 불러옵니다.")
    @app_commands.describe(character_name="불러올 캐릭터의 이름을 입력하세요.")
    async def load_profile(self, interaction: discord.Interaction, character_name: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT profile_data FROM profiles WHERE user_id = ? AND character_name = ?", (interaction.user.id, character_name))
        profile = cursor.fetchone()
        conn.close()
        if not profile:
            await interaction.response.send_message(f"'{character_name}'(이)라는 이름의 프로필을 찾을 수 없습니다. 이름을 정확히 입력했는지 확인해주세요.", ephemeral=True)
            return
        embed = discord.Embed(title=f"📜 프로필: {character_name}", description=profile[0], color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileManager(bot))