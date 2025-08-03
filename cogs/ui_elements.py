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
        # database.py에서 정의한 절대 경로를 사용
        from database import DB_FILE
        self.db_file = DB_FILE

    @discord.ui.button(label="💾 프로필 저장하기", style=discord.ButtonStyle.success, custom_id="save_profile")
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SaveProfileModal(self.db_file)
        await interaction.response.send_modal(modal)

class WorldviewSelectView(discord.ui.View):
    def __init__(self, cog, worldviews: list):
        super().__init__(timeout=180)
        self.cog = cog  # CharCreator 코그의 인스턴스
        
        options = [discord.SelectOption(label=name) for name in worldviews]
        
        # Select 메뉴에 콜백 함수를 직접 연결
        self.select = discord.ui.Select(
            placeholder="세계관을 선택하세요...",
            options=options,
            custom_id="start_worldview_select" # custom_id는 유지
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        """사용자가 세계관을 선택했을 때 호출되는 콜백"""
        # 로직을 View 내부에서 직접 처리
        await interaction.response.defer(thinking=True, ephemeral=True)

        user_id = interaction.user.id
        worldview = self.select.values[0]

        if user_id in self.cog.active_sessions:
            await interaction.followup.send("이미 진행 중인 캐릭터 생성 세션이 있습니다. 새로 시작하려면 먼저 `/quit`을 입력해주세요.", ephemeral=True)
            return

        # 세션 시작
        self.cog.active_sessions[user_id] = {
            "worldview": worldview,
            "messages": [],
            "last_message_time": time.time(),
            "timeout_notified": False
        }
        
        try:
            # DM 전송
            await interaction.user.send(f"'{worldview}' 세계관으로 캐릭터 생성을 시작합니다! DM으로 저와 자유롭게 대화하며 캐릭터를 만들어보세요. 대화를 마치고 싶으시면 언제든지 `/quit`을 입력해주세요.")
            
            # 후속 응답 전송
            await interaction.followup.send(content="캐릭터 생성 세션을 시작했습니다. DM을 확인해주세요!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(content="DM을 보낼 수 없습니다. 서버 설정에서 '서버 멤버가 보내는 다이렉트 메시지 허용'을 켜주세요.", ephemeral=True)
            if user_id in self.cog.active_sessions:
                del self.cog.active_sessions[user_id]
        except Exception as e:
            print(f"[Log] An unexpected error occurred in select_callback for user {user_id}: {e}")
            traceback.print_exc()
            await interaction.followup.send(content="세션 시작 중 예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
            if user_id in self.cog.active_sessions:
                del self.cog.active_sessions[user_id]

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