
import sqlite3
import os

DB_PATH = "test.db"

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check Agents
        try:
            cursor.execute("SELECT count(*) FROM agents")
            agent_count = cursor.fetchone()[0]
            print(f"✅ Agents table exists. Count: {agent_count}")
            if agent_count > 0:
                cursor.execute("SELECT name, role FROM agents LIMIT 5")
                print("   Sample agents:", cursor.fetchall())
        except sqlite3.Error as e:
            print(f"❌ Error checking agents table: {e}")

        # Check Teams
        try:
            cursor.execute("SELECT count(*) FROM teams")
            team_count = cursor.fetchone()[0]
            print(f"✅ Teams table exists. Count: {team_count}")
        except sqlite3.Error as e:
            print(f"❌ Error checking teams table: {e}")

        conn.close()
    except Exception as e:
        print(f"❌ Database connection error: {e}")

if __name__ == "__main__":
    check_db()
