import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
import traceback
from .ui_elements import (
    SaveProfileView, WorldviewSelectView, ProfileSelectView,
    ProfileManageView, WorldviewConfirmEditView, ProfileConfirmEditView
)

class ProfileManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # database.py에서 정의한 절대 경로를 사용
        from database import DB_FILE
        self.db_file = DB_FILE
        # 봇이 재시작되어도 View가 작동하도록 등록
        if not bot.persistent_views_added:
            bot.add_view(SaveProfileView())
            bot.persistent_views_added = True

    def _get_worldview_names(self):
        """데이터베이스에서 모든 세계관의 이름을 가져옵니다."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM worldviews ORDER BY id")
        worldviews = [row[0] for row in cursor.fetchall()]
        conn.close()
        return worldviews

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
            traceback.print_exc()
            await interaction.followup.send(f"❌ 오류: 세계관을 생성하는 중 문제가 발생했습니다: {e}")
        finally:
            if conn:
                conn.close()
                print(f"[Log] DB connection closed for creating worldview: {name}")

    @worldview_group.command(name="edit", description="드롭다운에서 수정할 세계관을 선택하세요.")
    async def worldview_edit_select(self, interaction: discord.Interaction):
        """수정할 세계관을 선택하는 드롭다운을 보여줍니다."""
        print(f"[Log] User {interaction.user.id} initiated /worldview edit command.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        worldviews = self._get_worldview_names()
        if not worldviews:
            await interaction.followup.send("수정할 세계관이 없습니다.", ephemeral=True)
            return
        
        view = WorldviewSelectView(worldviews, custom_id="manage_worldview_select")
        await interaction.followup.send("설명을 수정할 세계관을 선택하세요.", view=view, ephemeral=True)


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
            traceback.print_exc()
            await interaction.followup.send(f"❌ 오류: 세계관 목록을 불러오는 중 문제가 발생했습니다: {e}")
        finally:
            if conn:
                conn.close()
                print("[Log] DB connection closed for listing worldviews.")

    @worldview_group.command(name="view", description="드롭다운에서 볼 세계관을 선택하세요.")
    async def worldview_view_select(self, interaction: discord.Interaction):
        """상세 설명을 볼 세계관을 선택하는 드롭다운을 보여줍니다."""
        print(f"[Log] User {interaction.user.id} initiated /worldview view command.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        worldviews = self._get_worldview_names()
        if not worldviews:
            await interaction.followup.send("볼 수 있는 세계관이 없습니다.", ephemeral=True)
            return

        view = WorldviewSelectView(worldviews, custom_id="manage_worldview_select")
        await interaction.followup.send("상세 설명을 볼 세계관을 선택하세요.", view=view, ephemeral=True)

    async def _show_worldview_description(self, interaction: discord.Interaction, name: str):
        """특정 세계관의 상세 설명을 보여주는 내부 함수"""
        print(f"[Log] User {interaction.user.id} requested to view worldview: {name}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            print(f"[Log] DB connected for viewing worldview: {name}")
            cursor.execute("SELECT description FROM worldviews WHERE name = ?", (name,))
            result = cursor.fetchone()
            
            if not result:
                print(f"[Log] Worldview '{name}' not found for viewing.")
                await interaction.followup.send(f"'{name}' 세계관을 찾을 수 없습니다.", ephemeral=True)
                return
            
            description = result[0]
            embed = discord.Embed(
                title=f"🌌 세계관: {name}",
                description=description,
                color=discord.Color.purple()
            )
            
            print(f"[Log] Sending worldview description for '{name}' to user {interaction.user.id}.")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"[Log] Exception on viewing worldview '{name}': {e}")
            traceback.print_exc()
            await interaction.followup.send(f"❌ 오류: 세계관 정보를 불러오는 중 문제가 발생했습니다: {e}", ephemeral=True)
        finally:
            if conn:
                conn.close()
                print(f"[Log] DB connection closed for viewing worldview: {name}")


    async def _show_profile(self, interaction: discord.Interaction, character_name: str):
        """특정 캐릭터 프로필의 상세 내용을 보여주는 내부 함수"""
        print(f"[Log] User {interaction.user.id} requested to view profile: {character_name}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT profile_data FROM profiles WHERE user_id = ? AND character_name = ?", (interaction.user.id, character_name))
            result = cursor.fetchone()
            
            if not result:
                await interaction.followup.send(f"'{character_name}' 프로필을 찾을 수 없습니다.", ephemeral=True)
                return
            
            embed = discord.Embed(title=f"📜 프로필: {character_name}", description=result[0], color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ 오류: 프로필을 불러오는 중 문제가 발생했습니다: {e}", ephemeral=True)
        finally:
            if conn:
                conn.close()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """드롭다운 선택과 같은 상호작용을 처리합니다."""
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "manage_worldview_select":
            selected_name = interaction.data['values'][0]
            # The interaction is already deferred from the command, so we just process
            
            # We need to know what the original command was. We can check the message content.
            # This is a bit brittle, a better way might be to use different custom_ids for each command.
            original_message_content = interaction.message.content
            
            if "수정할 세계관" in original_message_content:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT description FROM worldviews WHERE name = ?", (selected_name,))
                result = cursor.fetchone()
                conn.close()
                if result:
                    view = WorldviewConfirmEditView(self.db_file, selected_name, result[0])
                    await interaction.followup.send(f"'{selected_name}' 세계관을 수정하려면 아래 버튼을 누르세요.", view=view, ephemeral=True)
                else:
                    await interaction.followup.send("오류: 해당 세계관을 찾을 수 없습니다.", ephemeral=True)

            elif "상세 설명을 볼 세계관" in original_message_content:
                await self._show_worldview_description(interaction, selected_name)

        elif custom_id == "profile_select":
            selected_profile = interaction.data['values'][0]
            view = ProfileManageView(selected_profile)
            await interaction.response.edit_message(content=f"**{selected_profile}** 프로필에 대해 무엇을 할까요?", view=view)

        elif custom_id == "view_profile":
            profile_name = interaction.message.content.split('**')[1] # 임시방편
            await interaction.response.defer(ephemeral=True)
            await self._show_profile(interaction, profile_name)

        elif custom_id == "edit_profile":
            await interaction.response.defer(ephemeral=True, thinking=True)
            profile_name = interaction.message.content.split('**')[1] # 임시방편
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT profile_data FROM profiles WHERE user_id = ? AND character_name = ?", (interaction.user.id, profile_name))
            result = cursor.fetchone()
            conn.close()
            if result:
                view = ProfileConfirmEditView(self.db_file, profile_name, result[0])
                await interaction.followup.send(f"'{profile_name}' 프로필을 수정하려면 아래 버튼을 누르세요.", view=view, ephemeral=True)
            else:
                await interaction.followup.send("오류: 해당 프로필을 찾을 수 없습니다.", ephemeral=True)

    def _get_profile_names(self, user_id: int):
        """데이터베이스에서 특정 사용자의 모든 프로필 이름을 가져옵니다."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT character_name FROM profiles WHERE user_id = ? ORDER BY id", (user_id,))
        profiles = [row[0] for row in cursor.fetchall()]
        conn.close()
        return profiles

    @app_commands.command(name="profiles", description="저장된 캐릭터 프로필을 관리합니다.")
    async def profiles_management(self, interaction: discord.Interaction):
        """관리할 프로필을 선택하는 드롭다운을 보여줍니다."""
        print(f"[Log] User {interaction.user.id} initiated /profiles command.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        profiles = self._get_profile_names(interaction.user.id)
        if not profiles:
            await interaction.followup.send("저장된 프로필이 없습니다.", ephemeral=True)
            return
        
        view = ProfileSelectView(profiles)
        await interaction.followup.send("관리할 캐릭터 프로필을 선택하세요.", view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileManager(bot))