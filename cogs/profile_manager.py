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

    @worldview_group.command(name="create", description="새로운 세계관을 생성합니다.")
    @app_commands.describe(name="새 세계관의 이름", description="새 세계관에 대한 간략한 설명")
    async def worldview_create(self, interaction: discord.Interaction, name: str, description: str):
        """새로운 세계관을 데이터베이스에 추가합니다."""
        print(f"[Log] User {interaction.user.id} attempting to create worldview: {name}")
        await interaction.response.defer(ephemeral=True)
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            print(f"[Log] DB connected for creating worldview: {name}")
            cursor.execute("INSERT INTO worldviews (name, description) VALUES (?, ?)", (name, description))
            conn.commit()
            print(f"[Log] Worldview '{name}' created successfully.")
            await interaction.followup.send(f"✅ 새로운 세계관 '{name}'(이)가 성공적으로 생성되었습니다!")
        except sqlite3.IntegrityError:
            print(f"[Log] IntegrityError on creating worldview '{name}': Already exists.")
            await interaction.followup.send(f"❌ 오류: '{name}'(이)라는 이름의 세계관이 이미 존재합니다.")
        except Exception as e:
            print(f"[Log] Exception on creating worldview '{name}': {e}")
            await interaction.followup.send(f"❌ 오류: 세계관을 생성하는 중 문제가 발생했습니다: {e}")
        finally:
            if conn:
                conn.close()
                print(f"[Log] DB connection closed for creating worldview: {name}")

    @worldview_group.command(name="edit", description="기존 세계관의 설명을 수정합니다.")
    @app_commands.describe(name="수정할 세계관 이름", description="새로운 세계관 설명")
    async def worldview_edit(self, interaction: discord.Interaction, name: str, description: str):
        print(f"[Log] User {interaction.user.id} attempting to edit worldview: {name}")
        await interaction.response.defer(ephemeral=True)
        conn = None  # conn을 try 블록 밖에서 초기화
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            print(f"[Log] DB connected for editing worldview: {name}")
            cursor.execute("UPDATE worldviews SET description = ? WHERE name = ?", (description, name))
            if cursor.rowcount > 0:
                conn.commit()
                print(f"[Log] Worldview '{name}' edited successfully.")
                await interaction.followup.send(f"✅ '{name}' 세계관의 설명이 수정되었습니다.")
            else:
                print(f"[Log] Worldview '{name}' not found for editing.")
                await interaction.followup.send(f"❌ '{name}' 세계관을 찾을 수 없습니다.")
        except Exception as e:
            print(f"[Log] Exception on editing worldview '{name}': {e}")
            await interaction.followup.send(f"❌ 오류: 세계관을 수정하는 중 문제가 발생했습니다: {e}")
        finally:
            if conn:
                conn.close()
                print(f"[Log] DB connection closed for editing worldview: {name}")

    @worldview_group.command(name="list", description="저장된 모든 세계관의 이름을 보여줍니다.")
    async def worldview_list(self, interaction: discord.Interaction):
        print(f"[Log] User {interaction.user.id} requested worldview list.")
        await interaction.response.defer(ephemeral=True)
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            print("[Log] DB connected for listing worldviews.")
            cursor.execute("SELECT name FROM worldviews ORDER BY id")
            worldviews = cursor.fetchall()
            
            if not worldviews:
                print("[Log] No worldviews found.")
                await interaction.followup.send("저장된 세계관이 없습니다.")
                return
                
            # 여러 줄의 문자열로 세계관 목록을 만듭니다.
            worldview_names = "\n".join([f"- {row[0]}" for row in worldviews])
            embed = discord.Embed(
                title="🌌 세계관 목록",
                description=worldview_names,
                color=discord.Color.purple()
            )
            
            print(f"[Log] Sending worldview list to user {interaction.user.id}.")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[Log] Exception on listing worldviews: {e}")
            await interaction.followup.send(f"❌ 오류: 세계관 목록을 불러오는 중 문제가 발생했습니다: {e}")
        finally:
            if conn:
                conn.close()
                print("[Log] DB connection closed for listing worldviews.")

    @worldview_group.command(name="view", description="특정 세계관의 상세 설명을 봅니다.")
    @app_commands.describe(name="상세 설명을 볼 세계관의 이름")
    async def worldview_view(self, interaction: discord.Interaction, name: str):
        print(f"[Log] User {interaction.user.id} requested to view worldview: {name}")
        await interaction.response.defer(ephemeral=True)
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            print(f"[Log] DB connected for viewing worldview: {name}")
            cursor.execute("SELECT description FROM worldviews WHERE name = ?", (name,))
            result = cursor.fetchone()
            
            if not result:
                print(f"[Log] Worldview '{name}' not found for viewing.")
                await interaction.followup.send(f"'{name}' 세계관을 찾을 수 없습니다.")
                return
            
            description = result[0]
            embed = discord.Embed(
                title=f"🌌 세계관: {name}",
                description=description,
                color=discord.Color.purple()
            )
            
            print(f"[Log] Sending worldview description for '{name}' to user {interaction.user.id}.")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[Log] Exception on viewing worldview '{name}': {e}")
            await interaction.followup.send(f"❌ 오류: 세계관 정보를 불러오는 중 문제가 발생했습니다: {e}")
        finally:
            if conn:
                conn.close()
                print(f"[Log] DB connection closed for viewing worldview: {name}")

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