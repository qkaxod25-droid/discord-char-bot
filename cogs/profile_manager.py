import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import traceback
from .ui_elements import WorldviewSelectView, ProfileSelectView, WorldviewEditModal
from database import DB_FILE

class ProfileManager(commands.Cog):
    """
    [REWRITE] 세계관 및 프로필 관리 Cog.
    문제를 유발하던 on_interaction 리스너를 제거하고, 모든 UI 로직을
    각각의 View 또는 View에 전달되는 콜백 함수 내부에서 처리합니다.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_file = DB_FILE

    def _get_worldview_names(self):
        """데이터베이스에서 모든 세계관의 이름을 가져옵니다."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM worldviews ORDER BY id")
        names = [row[0] for row in cursor.fetchall()]
        conn.close()
        return names

    def _get_profile_names(self, user_id: int):
        """데이터베이스에서 특정 사용자의 모든 프로필 이름을 가져옵니다."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT character_name FROM profiles WHERE user_id = ? ORDER BY id", (user_id,))
        names = [row[0] for row in cursor.fetchall()]
        conn.close()
        return names

    # --- 세계관 관리 명령어 그룹 ---
    worldview_group = app_commands.Group(name="worldview", description="세계관 프리셋을 관리합니다.")

    @worldview_group.command(name="create", description="새로운 세계관을 생성합니다.")
    @app_commands.describe(name="새 세계관의 이름", description="새 세계관에 대한 간략한 설명")
    async def worldview_create(self, interaction: discord.Interaction, name: str, description: str):
        await interaction.response.defer(ephemeral=True)
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO worldviews (name, description) VALUES (?, ?)", (name, description))
            conn.commit()
            conn.close()
            await interaction.followup.send(f"✅ 새로운 세계관 '{name}'(이)가 성공적으로 생성되었습니다!")
        except sqlite3.IntegrityError:
            await interaction.followup.send(f"❌ 오류: '{name}'(이)라는 이름의 세계관이 이미 존재합니다.")
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ 오류: 세계관을 생성하는 중 문제가 발생했습니다: {e}")

    @worldview_group.command(name="list", description="저장된 모든 세계관의 목록을 보여줍니다.")
    async def worldview_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        worldviews = self._get_worldview_names()
        if not worldviews:
            await interaction.followup.send("저장된 세계관이 없습니다.")
            return
        
        description = "\n".join([f"- {name}" for name in worldviews])
        embed = discord.Embed(title="🌌 세계관 목록", description=description, color=discord.Color.purple())
        await interaction.followup.send(embed=embed)

    @worldview_group.command(name="edit", description="기존 세계관의 설명을 수정합니다.")
    async def worldview_edit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        worldviews = self._get_worldview_names()
        if not worldviews:
            await interaction.followup.send("수정할 세계관이 없습니다.", ephemeral=True)
            return

        # 드롭다운에서 항목 선택 시 실행될 로직을 콜백 함수로 정의
        async def edit_callback(view: discord.ui.View, inner_interaction: discord.Interaction):
            selected_name = inner_interaction.data['values'][0]
            
            # 선택 후, 수정 모달(팝업)을 띄움
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT description FROM worldviews WHERE name = ?", (selected_name,))
            result = cursor.fetchone()
            conn.close()

            if result:
                current_description = result[0]
                modal = WorldviewEditModal(worldview_name=selected_name, current_description=current_description)
                await inner_interaction.response.send_modal(modal)
            else:
                await inner_interaction.response.send_message("오류: 해당 세계관을 찾을 수 없습니다.", ephemeral=True)

        # 재사용 가능한 View에 위에서 정의한 콜백 함수를 전달
        view = WorldviewSelectView(worldviews, callback_func=edit_callback)
        await interaction.followup.send("설명을 수정할 세계관을 선택하세요.", view=view, ephemeral=True)

    # --- 프로필 관리 명령어 ---
    @app_commands.command(name="profiles", description="저장된 캐릭터 프로필을 관리합니다.")
    async def profiles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        profiles = self._get_profile_names(interaction.user.id)
        if not profiles:
            await interaction.followup.send("저장된 프로필이 없습니다.", ephemeral=True)
            return
        
        # 프로필 선택 View를 전송. 이 View는 자체적으로 다음 단계(관리 버튼)를 처리함.
        view = ProfileSelectView(profiles)
        await interaction.followup.send("관리할 캐릭터 프로필을 선택하세요.", view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileManager(bot))