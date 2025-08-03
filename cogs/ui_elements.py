import discord
import sqlite3
import time
import traceback
from database import DB_FILE

# --- Modals (팝업 창) ---

class WorldviewEditModal(discord.ui.Modal, title="세계관 설명 수정"):
    def __init__(self, worldview_name: str, current_description: str):
        super().__init__()
        self.worldview_name = worldview_name
        self.description_input = discord.ui.TextInput(
            label=f"'{worldview_name}'의 새로운 설명",
            style=discord.TextStyle.paragraph,
            default=current_description,
            required=True,
            max_length=1024
        )
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_description = self.description_input.value
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE worldviews SET description = ? WHERE name = ?", (new_description, self.worldview_name))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"✅ '{self.worldview_name}' 세계관의 설명이 성공적으로 수정되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류: 설명을 수정하는 중 문제가 발생했습니다: {e}", ephemeral=True)

# --- Views (버튼, 드롭다운 메뉴) ---

class WorldviewSelectView(discord.ui.View):
    """
    [REWRITE V2] 세계관 선택을 위한 View.
    생성 시 콜백 함수를 받아, 다양한 상황(시작, 수정, 보기)에 재사용 가능하도록 설계.
    """
    def __init__(self, worldviews: list, callback_func):
        super().__init__(timeout=180)
        self.callback_func = callback_func
        options = [discord.SelectOption(label=name) for name in worldviews]
        self.select_menu = discord.ui.Select(
            placeholder="원하는 세계관을 선택하세요...",
            options=options,
            custom_id="generic_worldview_select"
        )
        self.select_menu.callback = self.on_select
        self.add_item(self.select_menu)

    async def on_select(self, interaction: discord.Interaction):
        # View를 생성할 때 전달받은 콜백 함수를 실행
        await self.callback_func(self, interaction)

class ProfileSelectView(discord.ui.View):
    """
    [REWRITE] 프로필 선택을 위한 View.
    선택 시 ProfileManageView를 보여줌.
    """
    def __init__(self, profiles: list):
        super().__init__(timeout=180)
        options = [discord.SelectOption(label=name) for name in profiles]
        self.select_menu = discord.ui.Select(
            placeholder="관리할 캐릭터 프로필을 선택하세요...",
            options=options,
            custom_id="profile_select_v2"
        )
        self.select_menu.callback = self.on_select
        self.add_item(self.select_menu)

    async def on_select(self, interaction: discord.Interaction):
        selected_profile = self.select_menu.values[0]
        # 응답을 수정하여, 선택된 프로필에 대한 관리 버튼(View)을 보여줌
        await interaction.response.edit_message(
            content=f"**{selected_profile}** 프로필에 대해 무엇을 할까요?",
            view=ProfileManageView(selected_profile)
        )

class ProfileManageView(discord.ui.View):
    """
    [REWRITE] 선택된 프로필을 관리(확인/수정/삭제)하기 위한 버튼 View.
    """
    def __init__(self, profile_name: str):
        super().__init__(timeout=180)
        self.profile_name = profile_name

    async def _get_profile_data(self, user_id: int) -> str | None:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT profile_data FROM profiles WHERE user_id = ? AND character_name = ?", (user_id, self.profile_name))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    @discord.ui.button(label="📜 프로필 확인", style=discord.ButtonStyle.secondary)
    async def view_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        profile_data = await self._get_profile_data(interaction.user.id)
        if profile_data:
            embed = discord.Embed(title=f"📜 프로필: {self.profile_name}", description=profile_data, color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("프로필을 찾을 수 없습니다.", ephemeral=True)

    @discord.ui.button(label="✏️ 프로필 수정", style=discord.ButtonStyle.primary)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 이 버튼은 현재 비활성화 상태입니다. 향후 프로필 수정 모달을 연결할 수 있습니다.
        button.disabled = True
        await interaction.response.send_message("프로필 수정 기능은 현재 준비 중입니다.", ephemeral=True)

# --- Char Creator 전용 View ---

class CharCreatorWorldviewSelectView(discord.ui.View):
    """
    [REWRITE] 캐릭터 생성(/start) 전용 세계관 선택 View.
    """
    def __init__(self, worldviews: list):
        super().__init__(timeout=180)
        options = [discord.SelectOption(label=name) for name in worldviews]
        self.select_menu = discord.ui.Select(
            placeholder="캐릭터를 생성할 세계관을 선택하세요...",
            options=options,
            custom_id="start_worldview_select_v3"
        )
        self.select_menu.callback = self.on_select
        self.add_item(self.select_menu)

    async def on_select(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True, ephemeral=True)
            bot = interaction.client
            user_id = interaction.user.id
            selected_worldview = self.select_menu.values[0]

            if user_id in bot.active_sessions:
                await interaction.followup.send("이미 진행 중인 세션이 있습니다. `/quit`으로 종료 후 다시 시도해주세요.", ephemeral=True)
                return

            bot.active_sessions[user_id] = {
                "worldview": selected_worldview,
                "messages": [],
                "last_message_time": time.time()
            }
            
            await interaction.user.send(f"'{selected_worldview}' 세계관으로 캐릭터 생성을 시작합니다! DM으로 대화해주세요.")
            await interaction.followup.send("캐릭터 생성 세션을 시작했습니다. DM을 확인해주세요!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("DM을 보낼 수 없습니다. 서버의 DM 설정을 확인해주세요.", ephemeral=True)
            if user_id in interaction.client.active_sessions:
                del interaction.client.active_sessions[user_id]
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send("세션 시작 중 오류가 발생했습니다.", ephemeral=True)
            if user_id in interaction.client.active_sessions:
                del interaction.client.active_sessions[user_id]