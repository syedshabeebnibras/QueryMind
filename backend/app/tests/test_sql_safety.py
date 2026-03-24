"""Tests for SQL safety enforcement."""

import pytest

from app.services.sql_safety import SQLSafetyError, check_sql_safety


class TestAllowedQueries:
    def test_simple_select(self) -> None:
        result = check_sql_safety("SELECT * FROM users")
        assert "SELECT" in result.upper()

    def test_select_with_where(self) -> None:
        result = check_sql_safety("SELECT name FROM users WHERE id = 1")
        assert "WHERE" in result.upper()

    def test_select_with_join(self) -> None:
        result = check_sql_safety(
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert "JOIN" in result.upper()

    def test_cte_select(self) -> None:
        result = check_sql_safety(
            "WITH active AS (SELECT * FROM users WHERE active = true) "
            "SELECT * FROM active"
        )
        assert "WITH" in result.upper()

    def test_aggregate_no_limit_required(self) -> None:
        result = check_sql_safety("SELECT COUNT(*) FROM users")
        # Aggregates should not have LIMIT forced
        assert "LIMIT" not in result.upper()

    def test_limit_enforcement(self) -> None:
        result = check_sql_safety("SELECT * FROM users")
        assert "LIMIT" in result.upper()

    def test_existing_limit_preserved(self) -> None:
        result = check_sql_safety("SELECT * FROM users LIMIT 10")
        assert "LIMIT" in result.upper()


class TestBlockedQueries:
    def test_insert(self) -> None:
        with pytest.raises(SQLSafetyError, match="Only SELECT"):
            check_sql_safety("INSERT INTO users (name) VALUES ('evil')")

    def test_update(self) -> None:
        with pytest.raises(SQLSafetyError, match="Only SELECT"):
            check_sql_safety("UPDATE users SET name = 'evil'")

    def test_delete(self) -> None:
        with pytest.raises(SQLSafetyError, match="Only SELECT"):
            check_sql_safety("DELETE FROM users")

    def test_drop(self) -> None:
        with pytest.raises(SQLSafetyError, match="Only SELECT"):
            check_sql_safety("DROP TABLE users")

    def test_alter(self) -> None:
        with pytest.raises(SQLSafetyError, match="Only SELECT"):
            check_sql_safety("ALTER TABLE users ADD COLUMN evil TEXT")

    def test_create(self) -> None:
        with pytest.raises(SQLSafetyError, match="Only SELECT"):
            check_sql_safety("CREATE TABLE evil (id INT)")

    def test_multi_statement(self) -> None:
        with pytest.raises(SQLSafetyError, match="Multiple statements"):
            check_sql_safety("SELECT 1; DROP TABLE users")

    def test_select_into(self) -> None:
        with pytest.raises(SQLSafetyError, match="INTO"):
            check_sql_safety("SELECT * INTO new_table FROM users")

    def test_empty(self) -> None:
        with pytest.raises(SQLSafetyError):
            check_sql_safety("")

    def test_blocked_function_pg_read_file(self) -> None:
        with pytest.raises(SQLSafetyError, match="Blocked function"):
            check_sql_safety("SELECT pg_read_file('/etc/passwd')")

    def test_blocked_function_pg_sleep(self) -> None:
        with pytest.raises(SQLSafetyError, match="Blocked function"):
            check_sql_safety("SELECT pg_sleep(100)")
