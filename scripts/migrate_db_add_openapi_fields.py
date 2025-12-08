"""
數據庫遷移腳本：為 tools 表添加 OpenAPI 支持字段
"""
import sys
sys.path.insert(0, '/app')

from api.database import engine
import sqlite3

def migrate_tools_table():
    """為 tools 表添加新字段"""
    conn = sqlite3.connect('/app/data/debate.db')
    cursor = conn.cursor()
    
    # 檢查字段是否已存在
    cursor.execute("PRAGMA table_info(tools)")
    columns = [col[1] for col in cursor.fetchall()]
    
    migrations = []
    
    if 'version' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN version VARCHAR DEFAULT 'v1'")
    if 'description' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN description TEXT")
    if 'provider' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN provider VARCHAR")
    if 'openapi_spec' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN openapi_spec JSON")
    if 'auth_type' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN auth_type VARCHAR")
    if 'auth_config' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN auth_config JSON")
    if 'rate_limit' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN rate_limit JSON")
    if 'cache_ttl' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN cache_ttl INTEGER DEFAULT 3600")
    if 'base_url' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN base_url VARCHAR")
    if 'timeout' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN timeout INTEGER DEFAULT 15")
    if 'created_at' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN created_at DATETIME")
    if 'updated_at' not in columns:
        migrations.append("ALTER TABLE tools ADD COLUMN updated_at DATETIME")
    
    if not migrations:
        print("✅ All columns already exist, no migration needed")
        conn.close()
        return
    
    print(f"🔄 Running {len(migrations)} migrations...")
    for migration in migrations:
        try:
            cursor.execute(migration)
            print(f"  ✅ {migration}")
        except Exception as e:
            print(f"  ⚠️  {migration} - {e}")
    
    conn.commit()
    conn.close()
    print("\n🎉 Migration completed!")

if __name__ == "__main__":
    migrate_tools_table()
