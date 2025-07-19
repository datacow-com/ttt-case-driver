import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, Optional
import json

DB_URL = os.environ.get("POSTGRES_URL", "postgresql://postgres:admin@localhost:5432/testcases")

class DBManager:
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = True

    def create_tables(self):
        with self.conn.cursor() as cur:
            cur.execute('''
            CREATE TABLE IF NOT EXISTS workflow_sessions (
                session_id UUID PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                input JSONB,
                config JSONB
            );
            CREATE TABLE IF NOT EXISTS node_results (
                id SERIAL PRIMARY KEY,
                session_id UUID,
                node_name TEXT,
                input JSONB,
                output JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                session_id UUID,
                node_name TEXT,
                feedback JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')

    def new_session(self, input_data: Dict[str, Any], config: Dict[str, Any]) -> str:
        session_id = str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workflow_sessions (session_id, input, config) VALUES (%s, %s, %s)",
                (session_id, json.dumps(input_data), json.dumps(config))
            )
        return session_id

    def save_node_result(self, session_id: str, node_name: str, input_data: Dict[str, Any], output_data: Dict[str, Any]):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO node_results (session_id, node_name, input, output) VALUES (%s, %s, %s, %s)",
                (session_id, node_name, json.dumps(input_data), json.dumps(output_data))
            )

    def get_node_result(self, session_id: str, node_name: str) -> Optional[Dict[str, Any]]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM node_results WHERE session_id=%s AND node_name=%s ORDER BY created_at DESC LIMIT 1",
                (session_id, node_name)
            )
            return cur.fetchone()

    def save_feedback(self, session_id: str, node_name: str, feedback: Dict[str, Any]):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (session_id, node_name, feedback) VALUES (%s, %s, %s)",
                (session_id, node_name, json.dumps(feedback))
            )

    def close(self):
        self.conn.close()
