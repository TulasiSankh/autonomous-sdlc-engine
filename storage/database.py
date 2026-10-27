"""SQLite database module for task persistence.

Uses Python's built-in sqlite3 module to manage task storage.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "tasks.db"


class Database:
    """SQLite database manager for the Autonomous SDLC Engine."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path: Path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a transactional SQLite connection with Row mapping."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Initializes database schema if tables do not exist and applies migrations."""
        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    workspace_id TEXT,
                    proposal_json TEXT,
                    application_status TEXT,
                    verification_status TEXT,
                    error_summary TEXT,
                    revision_count INTEGER DEFAULT 0
                );
                """
            )

            # Ensure backward-compatible migrations if table existed previously with fewer columns
            cursor = conn.execute("PRAGMA table_info(tasks);")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            columns_to_add = [
                ("workspace_id", "TEXT"),
                ("proposal_json", "TEXT"),
                ("application_status", "TEXT"),
                ("verification_status", "TEXT"),
                ("error_summary", "TEXT"),
                ("revision_count", "INTEGER DEFAULT 0"),
                ("task_type", "TEXT DEFAULT 'sdlc'"),
                ("execution_summary", "TEXT"),
                ("completed_at", "TEXT"),
            ]
            for col_name, col_type in columns_to_add:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type};")

            # Verification attempts historical log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_records (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    status TEXT NOT NULL,
                    exit_code INTEGER,
                    duration_seconds REAL NOT NULL,
                    stdout TEXT NOT NULL,
                    stderr TEXT NOT NULL,
                    output_truncated INTEGER NOT NULL,
                    timed_out INTEGER NOT NULL,
                    runner_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    error_message TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_verification_records_task_id 
                ON verification_records(task_id);
                """
            )

            # Computer task step executions log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_step_executions (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    step_description TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    parameters_json TEXT,
                    status TEXT NOT NULL,
                    output_json TEXT,
                    error_message TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    duration_seconds REAL,
                    requires_approval INTEGER DEFAULT 0,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_step_executions_task_id 
                ON task_step_executions(task_id);
                """
            )

    def save_task(
        self,
        task_id: str,
        task: str,
        plan_json: str,
        status: str,
        created_at: str,
        updated_at: str,
        workspace_id: Optional[str] = None,
        proposal_json: Optional[str] = None,
        application_status: Optional[str] = None,
        verification_status: Optional[str] = None,
        error_summary: Optional[str] = None,
        revision_count: int = 0,
        task_type: Optional[str] = "sdlc",
        execution_summary: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        """Inserts or updates a task record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, task, plan_json, status, created_at, updated_at,
                    workspace_id, proposal_json, application_status,
                    verification_status, error_summary, revision_count,
                    task_type, execution_summary, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    task_id,
                    task,
                    plan_json,
                    status,
                    created_at,
                    updated_at,
                    workspace_id,
                    proposal_json,
                    application_status,
                    verification_status,
                    error_summary,
                    revision_count,
                    task_type or "sdlc",
                    execution_summary,
                    completed_at,
                ),
            )

    def update_task_fields(
        self,
        task_id: str,
        updated_at: str,
        status: Optional[str] = None,
        workspace_id: Optional[str] = None,
        proposal_json: Optional[str] = None,
        application_status: Optional[str] = None,
        verification_status: Optional[str] = None,
        error_summary: Optional[str] = None,
        clear_error: bool = False,
        revision_count: Optional[int] = None,
        task_type: Optional[str] = None,
        execution_summary: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        """Updates specific lifecycle fields for an existing task record."""
        updates: List[str] = ["updated_at = ?"]
        params: List[Any] = [updated_at]

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if workspace_id is not None:
            updates.append("workspace_id = ?")
            params.append(workspace_id)
        if proposal_json is not None:
            updates.append("proposal_json = ?")
            params.append(proposal_json)
        if application_status is not None:
            updates.append("application_status = ?")
            params.append(application_status)
        if verification_status is not None:
            updates.append("verification_status = ?")
            params.append(verification_status)
        if error_summary is not None:
            updates.append("error_summary = ?")
            params.append(error_summary)
        elif clear_error:
            updates.append("error_summary = NULL")
        if revision_count is not None:
            updates.append("revision_count = ?")
            params.append(revision_count)
        if task_type is not None:
            updates.append("task_type = ?")
            params.append(task_type)
        if execution_summary is not None:
            updates.append("execution_summary = ?")
            params.append(execution_summary)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)

        params.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?;"

        with self.get_connection() as conn:
            conn.execute(sql, tuple(params))

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single task by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, task, plan_json, status, created_at, updated_at,
                       workspace_id, proposal_json, application_status,
                       verification_status, error_summary, revision_count,
                       task_type, execution_summary, completed_at
                FROM tasks WHERE id = ?;
                """,
                (task_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Retrieves all tasks sorted by creation date descending."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, task, plan_json, status, created_at, updated_at,
                       workspace_id, proposal_json, application_status,
                       verification_status, error_summary, revision_count,
                       task_type, execution_summary, completed_at
                FROM tasks ORDER BY created_at DESC;
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_task(self, task_id: str) -> bool:
        """Permanently deletes a task record and its related database logs.
        
        Preserves local computer files, original repos, and unrelated directories.
        
        Args:
            task_id: Unique task identifier.
            
        Returns:
            True if a task record was found and deleted, False otherwise.
        """
        with self.get_connection() as conn:
            conn.execute("DELETE FROM verification_records WHERE task_id = ?;", (task_id,))
            conn.execute("DELETE FROM task_step_executions WHERE task_id = ?;", (task_id,))
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))
            return cursor.rowcount > 0

    def save_step_execution(self, record: Dict[str, Any]) -> None:
        """Inserts or updates a task step execution record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO task_step_executions (
                    id, task_id, step_number, step_description, tool_name,
                    action, parameters_json, status, output_json, error_message,
                    started_at, completed_at, duration_seconds, requires_approval
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record["id"],
                    record["task_id"],
                    record["step_number"],
                    record["step_description"],
                    record["tool_name"],
                    record["action"],
                    record.get("parameters_json", "{}"),
                    record["status"],
                    record.get("output_json"),
                    record.get("error_message"),
                    record.get("started_at"),
                    record.get("completed_at"),
                    record.get("duration_seconds", 0.0),
                    1 if record.get("requires_approval") else 0,
                ),
            )

    def update_step_execution(
        self,
        step_id: str,
        status: str,
        output_json: Optional[str] = None,
        error_message: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Updates the status and output of a step execution."""
        updates = ["status = ?"]
        params: List[Any] = [status]

        if output_json is not None:
            updates.append("output_json = ?")
            params.append(output_json)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)
        if duration_seconds is not None:
            updates.append("duration_seconds = ?")
            params.append(duration_seconds)

        params.append(step_id)
        sql = f"UPDATE task_step_executions SET {', '.join(updates)} WHERE id = ?;"
        with self.get_connection() as conn:
            conn.execute(sql, tuple(params))

    def get_step_executions(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieves all step executions for a task ordered by step_number ASC."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, task_id, step_number, step_description, tool_name,
                       action, parameters_json, status, output_json, error_message,
                       started_at, completed_at, duration_seconds, requires_approval
                FROM task_step_executions
                WHERE task_id = ?
                ORDER BY step_number ASC;
                """,
                (task_id,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["requires_approval"] = bool(item.get("requires_approval"))
                results.append(item)
            return results

    def save_verification_record(self, record: Dict[str, Any]) -> None:
        """Inserts a historical verification record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO verification_records (
                    id, task_id, workspace_id, profile, status,
                    exit_code, duration_seconds, stdout, stderr,
                    output_truncated, timed_out, runner_id, timestamp, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record["id"],
                    record["task_id"],
                    record["workspace_id"],
                    record["profile"],
                    record["status"],
                    record.get("exit_code"),
                    record["duration_seconds"],
                    record.get("stdout", ""),
                    record.get("stderr", ""),
                    1 if record.get("output_truncated") else 0,
                    1 if record.get("timed_out") else 0,
                    record["runner_id"],
                    record["timestamp"],
                    record.get("error_message"),
                ),
            )

    def get_verification_records(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieves all verification records for a task, ordered by timestamp ASC."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, task_id, workspace_id, profile, status,
                       exit_code, duration_seconds, stdout, stderr,
                       output_truncated, timed_out, runner_id, timestamp, error_message
                FROM verification_records
                WHERE task_id = ?
                ORDER BY timestamp ASC;
                """,
                (task_id,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["output_truncated"] = bool(item["output_truncated"])
                item["timed_out"] = bool(item["timed_out"])
                results.append(item)
            return results

    def get_latest_verification_record(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent verification record for a task."""
        records = self.get_verification_records(task_id)
        return records[-1] if records else None


_db_instance: Optional[Database] = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """Returns the active Database instance, checking the SDLC_DB_PATH environment variable."""
    global _db_instance

    env_db_path = os.getenv("SDLC_DB_PATH")
    if db_path:
        return Database(db_path)
    if env_db_path:
        return Database(Path(env_db_path))

    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
