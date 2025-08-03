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

class ProfileSaveModal(discord.ui.Modal, title="프로필 저장"):
    def __init__(self, profile_data: str):
        super().__init__()
        self.profile_data = profile_data
        self.character_name_input = discord.ui.TextInput(
            label="캐릭터 이름",
            placeholder="저장할 캐릭터의 이름을 입력하세요.",
            required=True,
            max_length=50
        )
        self.add_item(self.character_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        character_name = self.character_name_input.value
        user_id = interaction.user.id
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            # 동일한 이름의 프로필이 있는지 확인 (덮어쓰기)
            cursor.execute("SELECT 1 FROM profiles WHERE user_id = ? AND character_name = ?", (user_id, character_name))
            if cursor.fetchone():
                cursor.execute("UPDATE profiles SET profile_data = ? WHERE user_id = ? AND character_name = ?", (self.profile_data, user_id, character_name))
                message = f"✅ 기존 프로필 '{character_name}'을(를) 덮어썼습니다."
            else:
                cursor.execute("INSERT INTO profiles (user_id, character_name, profile_data) VALUES (?, ?, ?)", (user_id, character_name, self.profile_data))
                message = f"✅ '{character_name}' 이름으로 프로필이 저장되었습니다."
            conn.commit()
            conn.close()
            await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"❌ 오류: 프로필을 저장하는 중 문제가 발생했습니다: {e}", ephemeral=True)
 
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
            
            # 생성 완료 버튼과 함께 첫 메시지 전송
            control_view = ConversationControlView()
            await interaction.user.send(
                f"'{selected_worldview}' 세계관으로 캐릭터 생성을 시작합니다! DM으로 대화해주세요.",
                view=control_view
            )
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

class ProfileSaveView(discord.ui.View):
    """
    [NEW] 생성된 프로필을 저장하기 위한 View.
    """
    def __init__(self, profile_data: str):
        super().__init__(timeout=None) # 저장 버튼은 타임아웃이 없어야 함
        self.profile_data = profile_data

    @discord.ui.button(label="💾 프로필 저장하기", style=discord.ButtonStyle.success, custom_id="save_profile_button")
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 버튼 클릭 시 ProfileSaveModal을 띄움
        await interaction.response.send_modal(ProfileSaveModal(self.profile_data))

class ConversationControlView(discord.ui.View):
    """
    [NEW] DM 대화 제어를 위한 View. 생성 완료 버튼을 포함합니다.
    """
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ 생성 완료", style=discord.ButtonStyle.success, custom_id="finish_creation_button")
    async def finish_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer() # 응답 대기

        bot = interaction.client
        user_id = interaction.user.id

        if user_id not in bot.active_sessions:
            await interaction.followup.send("진행 중인 생성 세션이 없습니다.", ephemeral=True)
            return

        session = bot.active_sessions[user_id]
        
        try:
            async with interaction.channel.typing():
                # 지시사항: 최종 템플릿만 출력하도록 하는 영어 지침
                final_prompt = "Based on the entire conversation history, complete the 'Final Profile Template'. Your output must only be the final, filled-out template text. Do not include any other conversational text, greetings, or explanations."
                session['messages'].append({"role": "user", "parts": [final_prompt]})

                # 기존 시스템 프롬프트와 대화 기록을 그대로 사용
                worldview_name = session.get('worldview')
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT description FROM worldviews WHERE name = ?", (worldview_name,))
                result = cursor.fetchone()
                conn.close()
                worldview_desc = result[0] if result else "설명을 찾을 수 없습니다."
                
                # 기존 시스템 지침을 그대로 사용
                system_instruction = f"""Your role is to help the user create a character by filling out a specific template.
Guide the user by asking questions to get the information needed for the template fields.
If the user asks to see the template, show them the exact Korean template below.

**World Setting:**
---
{worldview_desc}
---

**Final Profile Template (Your Goal):**

1. **기본 정보**
- 이름 / 나이 / 성별:
- 종족 / 출신:
- 외형 요약:

2. **배경 이야기 및 정체성**
- 간략한 배경 서사 (출신, 성장, 현재 위치):
- 성격 및 가치관:
- 현재 삶의 목표:

3. **능력 및 전투**
- 주요 능력 (지능/신체/기술 등 요약):
- 전투 스타일 / 전략:

4. **인물 관계**
- 주요 인맥 및 가족 요약:
- 주요 인물 1~2명과의 관계 설명 (선택):

Keep your tone encouraging and collaborative. Let's start by asking about the character's basic information.
"""
                
                model = genai.GenerativeModel(
                    'gemini-1.5-flash',
                    system_instruction=system_instruction
                )
                
                initial_bot_prompt = {"role": "model", "parts": ["어떤 캐릭터를 만들고 싶으신가요? 자유롭게 이야기해주세요."]}
                full_history = [initial_bot_prompt] + session['messages']

                response = await model.generate_content_async(full_history)
                profile_data = response.text

                # 최종 프로필과 저장 버튼 전송
                embed = discord.Embed(
                    title=f"'{worldview_name}' 세계관 기반 캐릭터 프로필",
                    description=profile_data,
                    color=discord.Color.gold()
                )
                embed.set_footer(text="아래 버튼을 눌러 프로필을 저장할 수 있습니다.")
                
                save_view = ProfileSaveView(profile_data=profile_data)
                await interaction.followup.send(embed=embed, view=save_view)

                # 원래 메시지의 버튼 비활성화
                button.disabled = True
                await interaction.edit_original_response(view=self)

                # 세션 종료
                del bot.active_sessions[user_id]

        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ 오류: 프로필을 생성하는 중 문제가 발생했습니다: {e}", ephemeral=True)