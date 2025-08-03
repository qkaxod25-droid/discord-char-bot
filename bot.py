import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import google.generativeai as genai
import asyncio
from database import initialize_database

# .env 파일에서 환경 변수 로드
load_dotenv()

# 데이터베이스 초기화
initialize_database()
print("[Log] Database initialized.")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini API 설정
genai.configure(api_key=GEMINI_API_KEY)

# 봇 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True

# 봇 객체 생성
bot = commands.Bot(command_prefix='/', intents=intents)
bot.last_generated_profiles = {} # key: user_id, value: {worldview_name, profile_data}
bot.persistent_views_added = False

@bot.event
async def on_ready():
    """봇이 준비되었을 때 실행됩니다."""
    print(f'{bot.user.name}이(가) 성공적으로 로그인했습니다!')
    print(f'봇 ID: {bot.user.id}')
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)}개의 슬래시 커맨드를 동기화했습니다.")
    except Exception as e:
        print(f"커맨드 동기화 중 오류 발생: {e}")

async def load_cogs():
    """cogs 폴더에서 모든 cog를 로드합니다."""
    # 스크립트의 현재 위치를 기준으로 cogs 폴더 경로를 설정합니다.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cogs_path = os.path.join(script_dir, 'cogs')
    
    for filename in os.listdir(cogs_path):
        if filename.endswith('.py') and filename != 'ui_elements.py':
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'{filename}을(를) 로드했습니다.')
            except Exception as e:
                print(f'{filename}을(를) 로드하는 중 오류가 발생했습니다: {e}')

async def main():
    """메인 함수"""
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)

if __name__ == '__main__':
    # asyncio.run()은 Windows에서 가끔 문제를 일으킬 수 있으므로,
    # 이벤트 루프 정책을 설정하여 해결합니다.
    if os.name == 'nt': # 'nt'는 Windows를 의미합니다.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())