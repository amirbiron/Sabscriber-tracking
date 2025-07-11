# db_manager.py
import sqlite3
import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Handles all database operations for the bot."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        logger.info(f"DatabaseManager initialized with path: {self.db_path}")

    def _execute(self, query: str, params: tuple = (), fetch: str = None):
        """Helper function to connect, execute, and close."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row # Makes fetching columns by name easy
                cursor = conn.cursor()
                cursor.execute(query, params)
                if fetch == 'one':
                    return cursor.fetchone()
                if fetch == 'all':
                    return cursor.fetchall()
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
            return None

    def init_database(self):
        """Initializes all tables in the database if they don't exist."""
        create_table_queries = [
            '''CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, service_name TEXT NOT NULL,
                amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'ILS', billing_day INTEGER NOT NULL,
                billing_cycle TEXT DEFAULT 'monthly', category TEXT DEFAULT 'other', notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1, auto_detected BOOLEAN DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY, timezone TEXT DEFAULT 'Asia/Jerusalem',
                notification_time TEXT DEFAULT '09:00', language TEXT DEFAULT 'he',
                currency_preference TEXT DEFAULT 'ILS', weekly_summary BOOLEAN DEFAULT 1,
                smart_suggestions BOOLEAN DEFAULT 1
            )''',
            '''CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                action TEXT NOT NULL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        for query in create_table_queries:
            self._execute(query)
        logger.info("Database initialized successfully.")

    def add_subscription(self, user_id: int, service_name: str, amount: float, currency: str, billing_day: int, category: str):
        query = '''INSERT INTO subscriptions (user_id, service_name, amount, currency, billing_day, category)
                   VALUES (?, ?, ?, ?, ?, ?)'''
        return self._execute(query, (user_id, service_name, amount, currency, billing_day, category))

    def get_user_subscriptions(self, user_id: int) -> List[sqlite3.Row]:
        query = 'SELECT * FROM subscriptions WHERE user_id = ? AND is_active = 1 ORDER BY billing_day ASC'
        return self._execute(query, (user_id,), fetch='all')

    def get_subscription_by_id(self, sub_id: int, user_id: int) -> Optional[sqlite3.Row]:
        query = 'SELECT * FROM subscriptions WHERE id = ? AND user_id = ? AND is_active = 1'
        return self._execute(query, (sub_id, user_id), fetch='one')

    def delete_subscription(self, sub_id: int, user_id: int):
        # We perform a "soft delete" by setting is_active to 0. This preserves data.
        query = 'UPDATE subscriptions SET is_active = 0 WHERE id = ? AND user_id = ?'
        self._execute(query, (sub_id, user_id))
        logger.info(f"Soft deleted subscription {sub_id} for user {user_id}")

    def get_stats_by_category(self, user_id: int) -> List[sqlite3.Row]:
        query = '''SELECT category, COUNT(*) as count, SUM(amount) as total
                   FROM subscriptions WHERE user_id = ? AND is_active = 1
                   GROUP BY category ORDER BY total DESC'''
        return self._execute(query, (user_id,), fetch='all')

    def log_user_action(self, user_id: int, action: str):
        query = 'INSERT INTO usage_stats (user_id, action) VALUES (?, ?)'
        self._execute(query, (user_id, action))

    def ensure_user_settings(self, user_id: int):
        if not self._execute('SELECT user_id FROM user_settings WHERE user_id = ?', (user_id,), fetch='one'):
            self._execute('INSERT INTO user_settings (user_id) VALUES (?)', (user_id,))
            logger.info(f"Created default settings for new user {user_id}")
    
    def get_user_settings(self, user_id: int) -> Optional[sqlite3.Row]:
        self.ensure_user_settings(user_id)
        return self._execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,), fetch='one')
