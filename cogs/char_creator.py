import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
import sqlite3
import traceback
from .ui_elements import CharCreatorWorldviewSelectView # CharCreator 전용 View를 임포트
from database import DB_FILE # database.py 에서 절대 경로를 가져옴

class CharCreator(commands.Cog):
    """
    [REWRITE] 캐릭터 생성 관련 명령어와 로직을 처리하는 Cog.
    상태 관리는 모두 bot 객체의 중앙 세션(bot.active_sessions)을 사용합니다.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_file = DB_FILE

    def get_worldviews(self):
        """데이터베이스에서 세계관 목록을 가져옵니다."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM worldviews")
            worldviews = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"[DB Log] Fetched worldviews: {worldviews}")
            return worldviews
        except Exception as e:
            print(f"DB에서 세계관을 가져오는 중 오류 발생: {e}")
            traceback.print_exc()
            return []

    @app_commands.command(name="start", description="캐릭터 생성을 시작합니다.")
    async def start(self, interaction: discord.Interaction):
        """사용 가능한 세계관 목록을 드롭다운으로 보여주고 선택하게 합니다."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        worldviews = self.get_worldviews()
        if not worldviews:
            await interaction.followup.send("생성된 세계관이 없습니다. 먼저 세계관을 만들어주세요.", ephemeral=True)
            return

        # /start 명령어 전용으로 만들어진, 독립적인 View를 생성하여 전달
        view = CharCreatorWorldviewSelectView(worldviews)
        await interaction.followup.send("캐릭터를 생성할 세계관을 선택해주세요.", view=view, ephemeral=True)

    @app_commands.command(name="quit", description="진행 중인 캐릭터 생성을 종료합니다.")
    async def quit(self, interaction: discord.Interaction):
        """캐릭터 생성 세션을 종료하는 명령어"""
        user_id = interaction.user.id
        # 중앙 세션(bot.active_sessions)을 확인하고 삭제
        if user_id in self.bot.active_sessions:
            del self.bot.active_sessions[user_id]
            await interaction.response.send_message("캐릭터 생성이 종료되었습니다. 또 이용해주세요!", ephemeral=True)
        else:
            await interaction.response.send_message("시작된 캐릭터 생성 세션이 없습니다.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """사용자 메시지를 감지하고 대화를 이어갑니다."""
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return

        user_id = message.author.id
        # 중앙 세션(bot.active_sessions)에 사용자가 있는지 확인
        if user_id in self.bot.active_sessions:
            async with message.channel.typing():
                session = self.bot.active_sessions[user_id]
                
                content = message.content
                session['messages'].append({"role": "user", "parts": [content]})

                # 데이터베이스에서 세계관 설명 가져오기
                worldview_name = session.get('worldview')
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT description FROM worldviews WHERE name = ?", (worldview_name,))
                result = cursor.fetchone()
                conn.close()

                worldview_desc = result[0] if result else "설명을 찾을 수 없습니다."
                
                # Gemini를 위한 시스템 지침 설정
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
                    model = genai.GenerativeModel(
                        'gemini-1.5-flash',
                        system_instruction=system_instruction
                    )
                    
                    initial_bot_prompt = {"role": "model", "parts": ["어떤 캐릭터를 만들고 싶으신가요? 자유롭게 이야기해주세요."]}
                    full_history = [initial_bot_prompt] + session['messages']

                    response = await model.generate_content_async(full_history)
                    bot_response = response.text
                    
                    session['messages'].append({"role": "model", "parts": [bot_response]})
                    
                    await message.channel.send(bot_response)

                except Exception as e:
                    print(f"Gemini API 호출 중 오류 발생: {e}")
                    traceback.print_exc()
                    await message.channel.send("죄송합니다, 아이디어를 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


async def setup(bot: commands.Bot):
    await bot.add_cog(CharCreator(bot))