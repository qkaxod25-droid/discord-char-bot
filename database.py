import sqlite3
import os

# 프로젝트 루트를 기준으로 절대 경로 생성
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(ROOT_DIR, "data", "profiles.db")

def initialize_database():
    """데이터베이스와 테이블을 초기화하고, 기본 세계관 프리셋을 추가합니다."""
    # data 디렉토리가 없으면 생성
    os.makedirs(os.path.join(ROOT_DIR, "data"), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 세계관 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS worldviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL
    )
    """)

    # 캐릭터 프로필 테이블 생성 (worldview_id 대신 worldview_name 사용)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        character_name TEXT NOT NULL,
        profile_data TEXT NOT NULL,
        worldview_name TEXT
    )
    """)

    # 세계관 프리셋이 비어있는지 확인
    cursor.execute("SELECT COUNT(*) FROM worldviews")
    count = cursor.fetchone()[0]

    # 비어있다면 3개의 프리셋 추가
    if count == 0:
        presets = [
            ('세계관1', '여기에 첫 번째 세계관 설명을 입력하세요.'),
            ('세계관2', '여기에 두 번째 세계관 설명을 입력하세요.'),
            ('세계관3', '여기에 세 번째 세계관 설명을 입력하세요.')
        ]
        cursor.executemany("INSERT INTO worldviews (name, description) VALUES (?, ?)", presets)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    initialize_database()
    print("Database initialized successfully with 3 worldview presets.")