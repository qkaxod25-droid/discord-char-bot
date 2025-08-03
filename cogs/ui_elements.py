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