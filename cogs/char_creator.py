import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
import sqlite3
import os
import asyncio
import time
import traceback
from .ui_elements import SaveProfileView

# 대화 세션을 저장할 딕셔너리
# key: user_id, value: {'worldview': str, 'messages': list, 'last_message_time': float, 'timeout_notified': bool}
active_sessions = {}

class CharCreator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_file = os.path.join("data", "profiles.db")
        self.timeout_task = self.bot.loop.create_task(self.check_inactive_sessions())

    def cog_unload(self):
        self.timeout_task.cancel()

    async def check_inactive_sessions(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = time.time()
            # RuntimeError를 피하기 위해 세션 키 목록의 복사본을 만들어 사용합니다.
            for user_id in list(active_sessions.keys()):
                session = active_sessions.get(user_id)
                if not session:
                    continue

                # 3분 (180초) 이상 응답이 없고, 아직 알림을 보내지 않은 경우
                if now - session.get('last_message_time', now) > 180 and not session.get('timeout_notified', False):
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await user.send("3분 동안 응답이 없어 대화가 중단되었습니다. 계속하시려면 메시지를 보내주시거나, 세션을 완전히 종료하려면 `/quit`을 입력해주세요.")
                        # 알림을 보냈다고 표시
                        active_sessions[user_id]['timeout_notified'] = True
                    except (discord.NotFound, discord.Forbidden):
                        # 유저를 찾을 수 없거나 DM을 보낼 수 없는 경우, 세션을 조용히 종료
                        if user_id in active_sessions:
                            del active_sessions[user_id]
                    except Exception as e:
                        print(f"타임아웃 알림 전송 중 오류 발생 (user: {user_id}): {e}")
                        traceback.print_exc()
            
            await asyncio.sleep(60) # 60초마다 체크

    def get_worldviews(self):
        """데이터베이스에서 세계관 목록을 가져옵니다."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM worldviews")
        worldviews = [row[0] for row in cursor.fetchall()]
        conn.close()
        return worldviews

    @app_commands.command(name="start", description="캐릭터 생성을 시작합니다. 드롭다운에서 세계관을 선택해주세요.")
    async def start(self, interaction: discord.Interaction):
        """사용 가능한 세계관 목록을 드롭다운으로 보여주고 선택하게 합니다."""
        print(f"[Log] User {interaction.user.id} initiated /start command.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        worldviews = self.get_worldviews()
        if not worldviews:
            await interaction.followup.send("생성된 세계관이 없습니다. 먼저 `/worldview create` 명령어로 세계관을 만들어주세요.", ephemeral=True)
            return

        view = WorldviewSelectView(worldviews, custom_id="start_worldview_select")
        await interaction.followup.send("캐릭터를 생성할 세계관을 선택해주세요.", view=view, ephemeral=True)

    async def start_session(self, interaction: discord.Interaction, worldview: str):
        """실제 캐릭터 생성 세션을 시작하는 내부 함수"""
        print("[Interaction Trace] Entered start_session.")
        user_id = interaction.user.id
        print(f"[Log] User {user_id} selected worldview '{worldview}' to start session.")

        if user_id in active_sessions:
            print(f"[Log] User {user_id} tried to start a session while another is active.")
            # The interaction has already been deferred, so we use followup.
            await interaction.followup.send("이미 진행 중인 캐릭터 생성 세션이 있습니다. 새로 시작하려면 먼저 `/quit`을 입력해주세요.", ephemeral=True)
            return

        # 세션 시작
        active_sessions[user_id] = {
            "worldview": worldview,
            "messages": [],
            "last_message_time": time.time(),
            "timeout_notified": False
        }
        print(f"[Log] Session started for user {user_id} with worldview: {worldview}")
        
        try:
            # 사용자에게 DM으로 안내 메시지 전송
            print("[Interaction Trace] Attempting to send DM.")
            await interaction.user.send(f"'{worldview}' 세계관으로 캐릭터 생성을 시작합니다! DM으로 저와 자유롭게 대화하며 캐릭터를 만들어보세요. 대화를 마치고 싶으시면 언제든지 `/quit`을 입력해주세요.")
            print("[Interaction Trace] DM sent successfully. Attempting to edit original response.")
            
            # 후속 응답으로 확인 메시지 전송 (ephemeral은 defer와 일치시켜야 함)
            await interaction.followup.send(content="캐릭터 생성 세션을 시작했습니다. DM을 확인해주세요!", ephemeral=True)
            print("[Interaction Trace] Follow-up response sent successfully.")
            print(f"[Log] DM sent to user {user_id} to start session.")
        except discord.Forbidden:
            print(f"[Log] Cannot send DM to user {user_id}. Deleting session.")
            traceback.print_exc()
            # DM 차단 시 후속 응답으로 사용자에게 안내
            await interaction.followup.send(content="DM을 보낼 수 없습니다. 서버 설정에서 '서버 멤버가 보내는 다이렉트 메시지 허용'을 켜주세요.", ephemeral=True)
            if user_id in active_sessions:
                del active_sessions[user_id]
        except Exception as e:
            print(f"[Log] An unexpected error occurred in start_session for user {user_id}: {e}")
            traceback.print_exc()
            # 예상치 못한 오류 발생 시 후속 응답으로 사용자에게 안내
            await interaction.followup.send(content="세션 시작 중 예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
            if user_id in active_sessions:
                del active_sessions[user_id]



    @app_commands.command(name="quit", description="진행 중인 캐릭터 생성을 종료합니다.")
    async def quit(self, interaction: discord.Interaction):
        """캐릭터 생성 세션을 종료하는 명령어"""
        user_id = interaction.user.id
        if user_id in active_sessions:
            del active_sessions[user_id]
            await interaction.response.send_message("캐릭터 생성이 종료되었습니다. 또 이용해주셔서 감사합니다!", ephemeral=True)
        else:
            await interaction.response.send_message("시작된 캐릭터 생성 세션이 없습니다.", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """드롭다운 선택과 같은 상호작용을 처리합니다."""
        try:
            if interaction.type == discord.InteractionType.component:
                custom_id = interaction.data.get("custom_id")
                print(f"[Interaction Trace] Received component interaction with custom_id: {custom_id}")
                if custom_id == "start_worldview_select":
                    print("[Interaction Trace] Matched 'start_worldview_select'. Deferring response.")
                    # Defer the interaction first to prevent timeouts
                    await interaction.response.defer(thinking=True, ephemeral=True)
                    print("[Interaction Trace] Response deferred. Preparing to start session.")
                    selected_worldview = interaction.data['values'][0]
                    await self.start_session(interaction, selected_worldview)
                    print("[Interaction Trace] start_session call completed.")
        except Exception as e:
            print(f"on_interaction 처리 중 오류 발생: {e}")
            traceback.print_exc()
            # Check if the interaction can still be responded to
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message("상호작용 처리 중 오류가 발생했습니다.", ephemeral=True)
                except discord.InteractionResponded:
                    await interaction.followup.send("상호작용 처리 중 오류가 발생했습니다.", ephemeral=True)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """사용자 메시지를 감지하고 대화를 이어갑니다."""
        # 봇 자신의 메시지, 또는 다른 명령어는 무시
        if message.author == self.bot.user or message.content.startswith('/'):
            return

        user_id = message.author.id
        if user_id in active_sessions:
            # DM 채널에서만 응답
            if isinstance(message.channel, discord.DMChannel):
                print(f"[Log] DM received from user {user_id}")
                async with message.channel.typing():
                    session = active_sessions[user_id]
                    
                    # 세션 정보 업데이트
                    session['last_message_time'] = time.time()
                    session['timeout_notified'] = False # 사용자가 응답했으므로 타임아웃 알림 상태 초기화
                    
                    content = message.content
                    session['messages'].append({"role": "user", "parts": [content]})
                    print(f"[Log] Message from {user_id} added to session history.")

                    # 데이터베이스에서 세계관 설명 가져오기
                    conn = sqlite3.connect(self.db_file)
                    cursor = conn.cursor()
                    cursor.execute("SELECT description FROM worldviews WHERE name = ?", (session['worldview'],))
                    result = cursor.fetchone()
                    conn.close()
                    worldview_desc = result[0] if result else "A generic fantasy world."
                    print(f"[Log] Worldview description for '{session['worldview']}' loaded for user {user_id}.")

                    # Gemini를 위한 시스템 지침 설정
                    # Gemini를 위한 시스템 지침 설정: 대화형 AI 역할 부여
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
                    
                    try:
                        print("[Log] Generating content with Gemini...")
                        model = genai.GenerativeModel(
                            'gemini-2.5-flash',
                            system_instruction=system_instruction
                        )
                        
                        # 봇의 첫 프롬프트를 포함한 전체 대화 내역 구성
                        initial_bot_prompt = {"role": "model", "parts": ["어떤 캐릭터를 만들고 싶으신가요? 자유롭게 이야기해주세요."]}
                        full_history = [initial_bot_prompt] + session['messages']

                        response = await model.generate_content_async(full_history)
                        bot_response = response.text
                        
                        # 봇의 응답을 세션에 기록
                        session['messages'].append({"role": "model", "parts": [bot_response]})
                        
                        await message.channel.send(bot_response)

                    except Exception as e:
                        print(f"Gemini API 호출 중 오류 발생: {e}")
                        traceback.print_exc()
                        await message.channel.send("죄송합니다, 아이디어를 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


async def setup(bot: commands.Bot):
    await bot.add_cog(CharCreator(bot))