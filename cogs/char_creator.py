import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
import sqlite3
import os
import asyncio
import time
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
            
            await asyncio.sleep(60) # 60초마다 체크

    def get_worldviews(self):
        """데이터베이스에서 세계관 목록을 가져옵니다."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM worldviews")
        worldviews = [row[0] for row in cursor.fetchall()]
        conn.close()
        return worldviews

    @app_commands.command(name="start", description="캐릭터 생성을 시작합니다. 세계관을 선택해주세요.")
    @app_commands.describe(worldview="캐릭터를 생성할 세계관을 선택하세요.")
    async def start(self, interaction: discord.Interaction, worldview: str):
        """캐릭터 생성 세션을 시작하는 명령어"""
        print(f"[Log] User {interaction.user.id} attempting to start session with worldview: {worldview}")
        worldviews = self.get_worldviews()
        if worldview not in worldviews:
            print(f"[Log] Invalid worldview '{worldview}' for user {interaction.user.id}")
            await interaction.response.send_message(f"'{worldview}'는 유효한 세계관이 아닙니다. 다음 중에서 선택해주세요: {', '.join(worldviews)}", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in active_sessions:
            print(f"[Log] User {user_id} tried to start a session while another is active.")
            await interaction.response.send_message("이미 진행 중인 캐릭터 생성 세션이 있습니다. 새로 시작하려면 먼저 `/quit`을 입력해주세요.", ephemeral=True)
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
            await interaction.user.send(f"'{worldview}' 세계관으로 캐릭터 생성을 시작합니다! DM으로 저와 자유롭게 대화하며 캐릭터를 만들어보세요. 대화를 마치고 싶으시면 언제든지 `/quit`을 입력해주세요.")
            # 상호작용에는 확인 메시지 전송
            await interaction.response.send_message("캐릭터 생성 세션을 시작했습니다. DM을 확인해주세요!", ephemeral=True)
            print(f"[Log] DM sent to user {user_id} to start session.")
        except discord.Forbidden:
            print(f"[Log] Cannot send DM to user {user_id}. Deleting session.")
            await interaction.response.send_message("DM을 보낼 수 없습니다. 봇의 DM을 허용해주세요.", ephemeral=True)
            if user_id in active_sessions:
                del active_sessions[user_id]

    @app_commands.command(name="generate", description="현재 대화 내용으로 캐릭터 프로필을 생성합니다.")
    async def generate(self, interaction: discord.Interaction):
        """대화 내용을 바탕으로 캐릭터 프로필을 생성합니다."""
        user_id = interaction.user.id
        if user_id not in active_sessions:
            await interaction.response.send_message("시작된 캐릭터 생성 세션이 없습니다. 먼저 `/start`를 이용해 대화를 시작해주세요.", ephemeral=True)
            return

        session = active_sessions[user_id]
        if not session['messages']:
            await interaction.response.send_message("프로필을 생성하기에는 대화 내용이 너무 적습니다. 캐릭터에 대해 더 이야기해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True) # 응답 시간을 확보합니다.

        try:
            # 데이터베이스에서 세계관 설명 가져오기
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT description FROM worldviews WHERE name = ?", (session['worldview'],))
            result = cursor.fetchone()
            conn.close()
            worldview_desc = result[0] if result else "A generic fantasy world."
            print(f"[Log] Worldview description for '{session['worldview']}' loaded for profile generation.")

            # 시스템 지침: 최종 프로필 생성을 위한 상세 지시
            system_instruction = f"""Your only job is to fill out the provided template based on the conversation.
- **Analyze the World Setting and Conversation History.**
- **You MUST use the Korean template provided below.**
- **Do NOT create new sections. Do NOT use English headers.**
- **Fill in the information for each field. If information is missing, leave it blank.**

**World Setting:**
---
{worldview_desc}
---

**Template to fill:**

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

**Rule for '인물 관계':** Only fill the '주요 인물 1~2명과의 관계 설명 (선택):' part if the user provided specific details about relationships. Otherwise, omit the line.
"""
            
            model = genai.GenerativeModel(
                'gemini-2.5-flash',
                system_instruction=system_instruction
            )
            
            # 봇의 첫 프롬프트를 포함한 전체 대화 내역 구성
            initial_bot_prompt = {"role": "model", "parts": ["어떤 캐릭터를 만들고 싶으신가요? 자유롭게 이야기해주세요."]}
            full_history = [initial_bot_prompt] + session['messages']

            response = await model.generate_content_async(full_history)
            
            # 생성된 프로필을 보기 좋은 임베드로 만듭니다.
            embed = discord.Embed(
                title="✨ 캐릭터 프로필 생성 완료!",
                description=response.text,
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"{interaction.user.display_name}님의 캐릭터")

            # 생성된 프로필을 봇의 전역 변수에 저장
            self.bot.last_generated_profiles[user_id] = {
                "worldview_name": session['worldview'],
                "profile_data": response.text
            }
            
            try:
                # 사용자에게 DM으로 프로필 전송
                await interaction.user.send(embed=embed, view=SaveProfileView())
                # 상호작용에는 확인 메시지 전송
                await interaction.followup.send("프로필이 생성되어 DM으로 전송되었습니다!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("DM을 보낼 수 없어 프로필을 전송하지 못했습니다. 봇의 DM을 허용해주세요.", ephemeral=True)

            # 프로필 생성 후 세션 종료
            if user_id in active_sessions:
                del active_sessions[user_id]

        except Exception as e:
            print(f"프로필 생성 중 오류 발생: {e}")
            await interaction.followup.send("죄송합니다, 프로필을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


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
                        await message.channel.send("죄송합니다, 아이디어를 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


async def setup(bot: commands.Bot):
    await bot.add_cog(CharCreator(bot))