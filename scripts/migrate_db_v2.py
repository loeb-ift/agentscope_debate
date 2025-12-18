"""
數據庫遷移腳本 v2：補齊 evidence_docs 與 checkpoints 表缺失的欄位。

主要變更：
- evidence_docs: 新增 title, source, snippet, fulltext_ref, timestamp, tool, citations
- checkpoints: 新增 plan_node_id
"""

import os
import sqlite3
import logging

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "test.db"

def migrate():
    if not os.path.exists(DB_PATH):
        logger.error(f"找不到數據庫檔案: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 遷移 evidence_docs 表
        logger.info("正在檢查 evidence_docs 表欄位...")
        cursor.execute("PRAGMA table_info(evidence_docs)")
        existing_cols = [row[1] for row in cursor.fetchall()]

        evidence_migrations = [
            ("title", "TEXT"),
            ("source", "TEXT"),
            ("snippet", "TEXT"),
            ("fulltext_ref", "TEXT"),
            ("timestamp", "DATETIME"),
            ("tool", "TEXT"),
            ("citations", "JSON")
        ]

        for col_name, col_type in evidence_migrations:
            if col_name not in existing_cols:
                logger.info(f"正在為 evidence_docs 新增欄位: {col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE evidence_docs ADD COLUMN {col_name} {col_type}")
            else:
                logger.info(f"evidence_docs 已存在欄位: {col_name}，跳過。")

        # 2. 遷移 checkpoints 表
        logger.info("正在檢查 checkpoints 表欄位...")
        cursor.execute("PRAGMA table_info(checkpoints)")
        existing_cols = [row[1] for row in cursor.fetchall()]

        if "plan_node_id" not in existing_cols:
            logger.info("正在為 checkpoints 新增欄位: plan_node_id (VARCHAR(100))")
            cursor.execute("ALTER TABLE checkpoints ADD COLUMN plan_node_id VARCHAR(100)")
        else:
            logger.info("checkpoints 已存在欄位: plan_node_id，跳過。")

        conn.commit()
        logger.info("✅ 遷移完成！")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ 遷移失敗: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
