import discord
import sqlite3
import os

class WorldviewEditModal(discord.ui.Modal, title="세계관 설명 수정"):
    def __init__(self, db_file: str, worldview_name: str, current_description: str):
        super().__init__()
        self.db_file = db_file
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
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE worldviews SET description = ? WHERE name = ?", (new_description, self.worldview_name))
            conn.commit()
            await interaction.response.send_message(f"✅ '{self.worldview_name}' 세계관의 설명이 성공적으로 수정되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류: 설명을 수정하는 중 문제가 발생했습니다: {e}", ephemeral=True)
        finally:
            conn.close()

class ProfileEditModal(discord.ui.Modal, title="프로필 수정"):
    def __init__(self, db_file: str, profile_name: str, current_data: str):
        super().__init__()
        self.db_file = db_file
        self.profile_name = profile_name
        self.profile_data_input = discord.ui.TextInput(
            label=f"'{profile_name}'의 프로필 내용",
            style=discord.TextStyle.paragraph,
            default=current_data,
            required=True
        )
        self.add_item(self.profile_data_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_data = self.profile_data_input.value
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE profiles SET profile_data = ? WHERE user_id = ? AND character_name = ?", (new_data, interaction.user.id, self.profile_name))
            conn.commit()
            await interaction.response.send_message(f"✅ '{self.profile_name}' 프로필이 성공적으로 수정되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류: 프로필을 수정하는 중 문제가 발생했습니다: {e}", ephemeral=True)
        finally:
            conn.close()

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
    def __init__(self, worldviews: list, custom_id: str = "worldview_select"):
        super().__init__(timeout=180)
        
        options = [discord.SelectOption(label=name) for name in worldviews]
        self.select = discord.ui.Select(placeholder="세계관을 선택하세요...", options=options, custom_id=custom_id)
        self.add_item(self.select)

class ProfileSelectView(discord.ui.View):
    def __init__(self, profiles: list):
        super().__init__(timeout=180)

        options = [discord.SelectOption(label=name) for name in profiles]
        self.select = discord.ui.Select(placeholder="캐릭터를 선택하세요...", options=options, custom_id="profile_select")
        self.add_item(self.select)

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

class WorldviewConfirmEditView(discord.ui.View):
    def __init__(self, db_file: str, worldview_name: str, description: str):
        super().__init__(timeout=180)
        self.db_file = db_file
        self.worldview_name = worldview_name
        self.description = description

    @discord.ui.button(label="✏️ 수정하기", style=discord.ButtonStyle.primary, custom_id="confirm_worldview_edit")
    async def confirm_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WorldviewEditModal(self.db_file, self.worldview_name, self.description)
        await interaction.response.send_modal(modal)

class ProfileConfirmEditView(discord.ui.View):
    def __init__(self, db_file: str, profile_name: str, profile_data: str):
        super().__init__(timeout=180)
        self.db_file = db_file
        self.profile_name = profile_name
        self.profile_data = profile_data

    @discord.ui.button(label="✏️ 수정하기", style=discord.ButtonStyle.primary, custom_id="confirm_profile_edit")
    async def confirm_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ProfileEditModal(self.db_file, self.profile_name, self.profile_data)
        await interaction.response.send_modal(modal)