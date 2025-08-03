import discord
import sqlite3
import os

class SaveProfileModal(discord.ui.Modal, title="캐릭터 이름 정하기"):
    character_name = discord.ui.TextInput(
        label="캐릭터의 이름을 입력하세요",
        placeholder="예: 아서 펜드래건",
        required=True,
        max_length=50
    )

    def __init__(self, db_file: str):
        super().__init__()
        self.db_file = db_file

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        profile_info = interaction.client.last_generated_profiles.get(user_id)

        if not profile_info:
            await interaction.response.send_message("저장할 프로필 정보를 찾을 수 없습니다. 다시 생성해주세요.", ephemeral=True)
            return

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO profiles (user_id, character_name, profile_data, worldview_name) VALUES (?, ?, ?, ?)",
                (user_id, self.character_name.value, profile_info['profile_data'], profile_info['worldview_name'])
            )
            conn.commit()
            await interaction.response.send_message(f"✅ 캐릭터 '{self.character_name.value}'(이)가 성공적으로 저장되었습니다!", ephemeral=True)
            if user_id in interaction.client.last_generated_profiles:
                del interaction.client.last_generated_profiles[user_id]
        except sqlite3.IntegrityError:
            await interaction.response.send_message("오류: 이미 같은 이름의 캐릭터가 존재합니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"저장 중 오류가 발생했습니다: {e}", ephemeral=True)
        finally:
            conn.close()

class SaveProfileView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.db_file = os.path.join("data", "profiles.db")

    @discord.ui.button(label="💾 프로필 저장하기", style=discord.ButtonStyle.success, custom_id="save_profile")
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SaveProfileModal(self.db_file)
        await interaction.response.send_modal(modal)

class WorldviewSelectView(discord.ui.View):
    def __init__(self, worldviews: list, callback_command: str):
        super().__init__(timeout=180)
        self.callback_command = callback_command
        
        options = [discord.SelectOption(label=name) for name in worldviews]
        self.select = discord.ui.Select(placeholder="세계관을 선택하세요...", options=options, custom_id="worldview_select")
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        selected_worldview = self.select.values[0]
        # 선택된 세계관으로 원래 명령어를 다시 호출하는 것처럼 처리 (실제 구현은 각 cog에서)
        # 예: /start worldview={selected_worldview}
        await interaction.response.defer() # 응답을 다음 단계로 넘김
        # 이 View를 호출한 곳에서 followup을 통해 응답을 처리해야 함

class ProfileSelectView(discord.ui.View):
    def __init__(self, profiles: list, callback_command: str):
        super().__init__(timeout=180)
        self.callback_command = callback_command

        options = [discord.SelectOption(label=name) for name in profiles]
        self.select = discord.ui.Select(placeholder="캐릭터를 선택하세요...", options=options, custom_id="profile_select")
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        selected_profile = self.select.values[0]
        await interaction.response.defer()

class ProfileManageView(discord.ui.View):
    def __init__(self, profile_name: str):
        super().__init__(timeout=180)
        self.profile_name = profile_name

    @discord.ui.button(label="📜 프로필 확인", style=discord.ButtonStyle.secondary, custom_id="view_profile")
    async def view_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 이 버튼의 로직은 profile_manager.py의 on_interaction에서 처리됩니다.
        await interaction.response.defer()

    @discord.ui.button(label="✏️ 프로필 수정", style=discord.ButtonStyle.primary, custom_id="edit_profile")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 이 버튼의 로직은 profile_manager.py의 on_interaction에서 처리됩니다.
        await interaction.response.defer()