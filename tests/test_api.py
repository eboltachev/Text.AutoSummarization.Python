import os
import re
import shutil
import subprocess
from contextlib import closing
from time import sleep
from typing import Any, Dict, Iterable, List
from uuid import uuid4

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
import pytest
import requests
from conftest import authorization
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.asyncio
class TestAPI:
    def setup_class(self):
        if shutil.which("docker") is None:
            pytest.skip("Docker is required to run integration tests", allow_module_level=True)
        self._sleep = 1
        self._timeout = 30
        self._compose_file = "docker-compose.yml"
        self._content_file_path = "dev/content.txt"
        os.makedirs("dev", exist_ok=True)
        self._cwd = os.getcwd()
        with open(self._content_file_path, "w") as content_file:
            content_file.write("**Logs**\n\n")
        with open(self._content_file_path, "a") as content_file:
            subprocess.run(
                ["docker", "compose", "-f", self._compose_file, "up", "--build", "-d"],
                stdout=content_file,
                stderr=content_file,
            )
        with open(self._content_file_path, "a") as content_file:
            subprocess.run(
                [
                    "printdirtree",
                    "--exclude-dir",
                    "tests",
                    "hf_models",
                    ".venv",
                    "uv.lock",
                    ".pytest_cache",
                    ".mypy_cache",
                    "--show-contents",
                ],
                cwd=self._cwd,
                stdout=content_file,
                stderr=content_file,
            )
        self._api_host = os.environ.get("AUTO_SUMMARIZATION_API_HOST", "localhost")
        self._api_port = os.environ.get("AUTO_SUMMARIZATION_API_PORT", 8000)
        self._api_url = f"http://{self._api_host}:{self._api_port}"
        self._prefix = os.environ.get("AUTO_SUMMARIZATION_URL_PREFIX", "/v1")
        self._headers = {authorization: str(uuid4())}
        self._id_pattern = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"

        db_host = os.environ.get("AUTO_SUMMARIZATION_DB_HOST", "localhost")
        self._db_host = self._normalize_host(db_host)
        self._db_port = int(os.environ.get("AUTO_SUMMARIZATION_DB_PORT", 5432))
        self._db_name = os.environ.get("AUTO_SUMMARIZATION_DB_NAME", "autosummarization")
        self._db_user = os.environ.get("AUTO_SUMMARIZATION_DB_USER", "autosummary")
        self._db_password = os.environ.get("AUTO_SUMMARIZATION_DB_PASSWORD")
        if not self._db_password:
            pytest.skip("Database credentials are required to run integration tests", allow_module_level=True)
        self._db_connect_kwargs = {
            "host": self._db_host,
            "port": self._db_port,
            "dbname": self._db_name,
            "user": self._db_user,
            "password": self._db_password,
        }

        connection = False
        timeout_counter = 0
        while not connection:
            try:
                requests.get(self._api_url)
                connection = True
            except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
                sleep(self._sleep)
                timeout_counter += 1
                if timeout_counter > self._timeout:
                    with open(self._content_file_path, "a") as content_file:
                        subprocess.run(
                            ["docker", "compose", "-f", self._compose_file, "logs"],
                            cwd=self._cwd,
                            stdout=content_file,
                            stderr=content_file,
                        )
                    subprocess.run(
                        ["docker", "compose", "-f", self._compose_file, "down", "-v"],
                        cwd=self._cwd,
                        stdout=open(os.devnull, "w"),
                        stderr=subprocess.STDOUT,
                    )
                    raise Exception("Setup timeout")

        db_ready = False
        timeout_counter = 0
        while not db_ready:
            try:
                with closing(psycopg2.connect(**self._db_connect_kwargs)) as connection:
                    connection.close()
                db_ready = True
            except OperationalError:
                sleep(self._sleep)
                timeout_counter += 1
                if timeout_counter > self._timeout:
                    pytest.skip("Database is not ready for integration tests", allow_module_level=True)

    def teardown_class(self):
        with open(self._content_file_path, "a") as content_file:
            content_file.write(f"\n\n**Logs:**\n\n")
        with open(self._content_file_path, "a") as content_file:
            subprocess.run(
                ["docker", "compose", "-f", self._compose_file, "logs"],
                cwd=self._cwd,
                stdout=content_file,
                stderr=content_file,
            )
        subprocess.run(
            ["docker", "compose", "-f", self._compose_file, "down", "-v"],
            cwd=self._cwd,
            stdout=open(os.devnull, "w"),
            stderr=subprocess.STDOUT,
        )

    @staticmethod
    def _normalize_host(host: str | None) -> str:
        if not host or host in {"db", "0.0.0.0"}:
            return "localhost"
        return host

    def _db_execute(self, query: str, params: Iterable[Any] | None = None) -> List[Dict[str, Any]]:
        with closing(psycopg2.connect(**self._db_connect_kwargs)) as connection:
            connection.autocommit = True
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, tuple(params or ()))
                if cursor.description is None:
                    return []
                return list(cursor.fetchall())

    def _db_fetchone(self, query: str, params: Iterable[Any] | None = None) -> Dict[str, Any] | None:
        results = self._db_execute(query, params)
        return results[0] if results else None

    async def test_docs(self):
        response = requests.get(f"{self._api_url}/docs")
        assert response.status_code == 200
        assert "FastAPI - Swagger UI" in response.text

    async def test_health(self):
        response = requests.get(f"{self._api_url}/health")
        assert response.status_code == 200
        assert {"status": "ok"} == response.json()

    async def test_analyze_types_and_load_document(self):
        response = requests.get(f"{self._api_url}{self._prefix}/analysis/analyze_types")
        assert response.status_code == 200
        payload = response.json()
        categories = payload.get("categories")
        choices = payload.get("choices")
        assert categories == ["Экономика", "Спорт", "Путешествия"]
        assert choices == ["Аннотация", "Объекты", "Тональность", "Классификация", "Выводы"]

        templates = self._db_execute(
            "SELECT category_index, category, choice_index, choice_name, model_type "
            "FROM analysis_templates ORDER BY category_index, choice_index"
        )
        assert len(templates) == len(categories) * len(choices)
        assert {template["choice_name"] for template in templates} >= set(choices)
        universal_templates = [
            template
            for template in templates
            if (template["model_type"] or "").upper() == "UNIVERSAL"
        ]
        pretrained_templates = [
            template
            for template in templates
            if (template["model_type"] or "").upper() == "PRETRAINED"
        ]
        assert universal_templates, "Expected at least one UNIVERSAL template in the database"
        assert pretrained_templates, "Expected at least one PRETRAINED template in the database"

        for template in templates:
            if template["choice_name"] == "Классификация":
                if template["category"] == "Спорт":
                    assert template["model_type"] == "PRETRAINED"
                else:
                    assert template["model_type"] == "UNIVERSAL"

        files = {"document": ("sample.txt", "Это тестовый документ для проверки загрузки.", "text/plain")}
        response = requests.post(
            f"{self._api_url}{self._prefix}/analysis/load_document",
            headers=self._headers,
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert "документ" in data.get("text").lower()

        invalid_files = {"document": ("malware.exe", b"binary", "application/octet-stream")}
        invalid_response = requests.post(
            f"{self._api_url}{self._prefix}/analysis/load_document",
            headers=self._headers,
            files=invalid_files,
        )
        assert invalid_response.status_code == 400
        assert "Unsupported document format" in invalid_response.text

    async def test_session_create_performs_analysis(self):
        user_id = str(uuid4())
        headers = {authorization: user_id}

        text = "Российский рынок акций вырос на 5%, инвесторы ожидают снижения ставки."
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/create",
            headers=headers,
            json={"text": text, "category": 0, "choices": [0, 3, 4]},
        )
        assert response.status_code == 200
        creation_payload = response.json()
        assert creation_payload["error"] is None
        economy_content = creation_payload.get("content") or {}
        assert isinstance(economy_content.get("short_summary"), str)
        assert isinstance(economy_content.get("full_summary"), str)

        page_response = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/fetch_page",
            headers=headers,
        )
        assert page_response.status_code == 200
        sessions_payload = page_response.json().get("sessions", [])
        assert len(sessions_payload) == 1
        economy_session = sessions_payload[0]
        assert re.match(self._id_pattern, economy_session.get("session_id"))
        assert economy_session.get("text") == text
        assert economy_session.get("content", {}).get("short_summary") == economy_content.get("short_summary")

        db_user = self._db_fetchone("SELECT user_id, temporary FROM users WHERE user_id = %s", (user_id,))
        assert db_user is not None
        assert db_user["user_id"] == user_id
        assert db_user["temporary"] is True

        economy_session_id = economy_session.get("session_id")
        db_session = self._db_fetchone(
            "SELECT short_summary, entities, sentiments, classifications, full_summary, version, user_id "
            "FROM sessions WHERE session_id = %s",
            (economy_session_id,),
        )
        assert db_session is not None
        assert db_session["user_id"] == user_id
        for key in ("short_summary", "entities", "sentiments", "classifications", "full_summary"):
            if economy_content.get(key) is not None:
                assert db_session[key] == economy_content[key]

        sport_text = "Команда одержала победу со счетом 2:1, болельщики были в восторге."
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/create",
            headers=headers,
            json={"text": sport_text, "category": 1, "choices": [1, 3]},
        )
        assert response.status_code == 200
        sport_payload = response.json()
        assert sport_payload["error"] is None
        sport_content = sport_payload.get("content") or {}
        assert isinstance(sport_content.get("entities"), str)

        updated_page = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/fetch_page",
            headers=headers,
        )
        assert updated_page.status_code == 200
        sessions = updated_page.json().get("sessions", [])
        assert len(sessions) == 2
        sessions_by_text = {session["text"]: session for session in sessions}
        assert set(sessions_by_text.keys()) == {text, sport_text}

        sport_session = sessions_by_text[sport_text]
        sport_session_id = sport_session.get("session_id")
        assert re.match(self._id_pattern, sport_session_id)

        db_sport_session = self._db_fetchone(
            "SELECT classifications, entities, user_id FROM sessions WHERE session_id = %s",
            (sport_session_id,),
        )
        assert db_sport_session is not None
        assert db_sport_session["user_id"] == user_id
        for field in ("classifications", "entities"):
            if sport_content.get(field) is not None:
                assert db_sport_session[field] == sport_content[field]

        search_response = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/search",
            headers=headers,
            params={"query": "рынок акций"},
        )
        assert search_response.status_code == 200
        search_payload = search_response.json().get("results", [])
        assert search_payload, "Expected search results for economy session query"
        assert search_payload[0]["session_id"] == economy_session_id
        assert search_payload[0]["score"] >= search_payload[-1]["score"]

        sport_search = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/search",
            headers=headers,
            params={"query": "болельщики"},
        )
        assert sport_search.status_code == 200
        sport_results = sport_search.json().get("results", [])
        assert sport_results, "Expected search results for sport session query"
        assert sport_results[0]["session_id"] == sport_session_id

        invalid_search = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/search",
            headers=headers,
            params={"query": "   "},
        )
        assert invalid_search.status_code == 400

        cleanup = requests.delete(
            f"{self._api_url}{self._prefix}/user/delete_user",
            json={"user_id": user_id},
        )
        assert cleanup.status_code == 200
        assert cleanup.json().get("status") in {"deleted", "not_found"}

        assert self._db_fetchone("SELECT 1 FROM users WHERE user_id = %s", (user_id,)) is None
        assert self._db_execute("SELECT 1 FROM sessions WHERE user_id = %s", (user_id,)) == []

    async def test_users_and_sessions(self):
        user_id = self._headers[authorization]
        response = requests.get(f"{self._api_url}{self._prefix}/user/get_users")
        assert response.status_code == 200
        assert response.json().get("users") == []

        response = requests.post(
            f"{self._api_url}{self._prefix}/user/create_user",
            json={"user_id": user_id, "temporary": False},
        )
        assert response.status_code == 200
        assert response.json().get("status") == "created"

        db_user = self._db_fetchone(
            "SELECT user_id, temporary, started_using_at, last_used_at FROM users WHERE user_id = %s",
            (user_id,),
        )
        assert db_user is not None
        assert db_user["temporary"] is False
        assert isinstance(db_user["started_using_at"], float)
        assert isinstance(db_user["last_used_at"], float)

        response = requests.post(
            f"{self._api_url}{self._prefix}/user/create_user",
            json={"user_id": user_id, "temporary": False},
        )
        assert response.status_code == 200
        assert response.json().get("status") == "exist"

        response = requests.get(f"{self._api_url}{self._prefix}/user/get_users")
        users = response.json().get("users")
        assert len(users) == 1
        info = users[0]
        assert re.match(self._id_pattern, info.get("user_id"))
        assert info.get("temporary") is False
        assert isinstance(info.get("started_using_at"), float)
        assert isinstance(info.get("last_used_at"), float)

        payload = {
            "text": "Путешествие было незабываемым.",
            "category": 2,
            "choices": [0, 4],
        }
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/create",
            headers=self._headers,
            json=payload,
        )
        assert response.status_code == 200
        create_payload = response.json()
        assert create_payload["error"] is None
        content = create_payload.get("content") or {}
        assert isinstance(content.get("short_summary"), str)
        assert isinstance(content.get("full_summary"), str)

        response = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/fetch_page",
            headers=self._headers,
        )
        assert response.status_code == 200
        sessions = response.json().get("sessions")
        assert len(sessions) == 1
        session_info = sessions[0]
        session_id = session_info.get("session_id")
        assert re.match(self._id_pattern, session_id)
        assert session_info.get("content", {}).get("short_summary") == content.get("short_summary")

        db_session = self._db_fetchone(
            "SELECT user_id, version, short_summary, full_summary FROM sessions WHERE session_id = %s",
            (session_id,),
        )
        assert db_session is not None
        assert db_session["user_id"] == user_id
        assert db_session["short_summary"] == content["short_summary"]

        update_payload = {
            "session_id": session_id,
            "text": payload["text"],
            "category": payload["category"],
            "choices": payload["choices"],
            "version": session_info.get("version"),
        }
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_summarization",
            headers=self._headers,
            json=update_payload,
        )
        assert response.status_code == 200
        update_content = response.json().get("content") or {}
        assert set(update_content.keys()) <= {
            "short_summary",
            "entities",
            "sentiments",
            "classifications",
            "full_summary",
        }
        assert isinstance(update_content.get("short_summary"), str)

        refreshed_page = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/fetch_page",
            headers=self._headers,
        )
        assert refreshed_page.status_code == 200
        refreshed_session = refreshed_page.json().get("sessions")[0]
        assert refreshed_session["version"] == session_info.get("version") + 1
        assert refreshed_session["content"]["short_summary"] == update_content.get("short_summary")

        stale_update = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_summarization",
            headers=self._headers,
            json=update_payload,
        )
        assert stale_update.status_code == 400
        assert "Version mismatch" in stale_update.text

        db_session_after_update = self._db_fetchone(
            "SELECT version FROM sessions WHERE session_id = %s",
            (session_id,),
        )
        assert db_session_after_update is not None
        assert db_session_after_update["version"] == refreshed_session["version"]

        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_title",
            headers=self._headers,
            json={
                "session_id": session_id,
                "title": "Новый заголовок",
                "version": refreshed_session["version"],
            },
        )
        assert response.status_code == 200
        update_title_payload = response.json()
        assert update_title_payload["title"] == "Новый заголовок"
        assert update_title_payload["version"] == refreshed_session["version"] + 1

        db_session_after_title = self._db_fetchone(
            "SELECT title, version FROM sessions WHERE session_id = %s",
            (session_id,),
        )
        assert db_session_after_title is not None
        assert db_session_after_title["title"] == "Новый заголовок"
        assert db_session_after_title["version"] == update_title_payload["version"]

        response = requests.delete(
            f"{self._api_url}{self._prefix}/chat_session/delete",
            headers=self._headers,
            json={"session_id": session_id},
        )
        assert response.status_code == 200
        assert response.json().get("status") == "SUCCESS"

        assert self._db_fetchone("SELECT 1 FROM sessions WHERE session_id = %s", (session_id,)) is None

        response = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/fetch_page",
            headers=self._headers,
        )
        assert response.status_code == 200
        assert response.json().get("sessions") == []

        cleanup = requests.delete(
            f"{self._api_url}{self._prefix}/user/delete_user",
            json={"user_id": user_id},
        )
        assert cleanup.status_code == 200
        assert cleanup.json().get("status") in {"deleted", "not_found"}
        assert self._db_fetchone("SELECT 1 FROM users WHERE user_id = %s", (user_id,)) is None

    async def test_session_create_requires_authorization(self):
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/create",
            json={"text": "Без авторизации", "category": 0, "choices": [0]},
        )
        assert response.status_code == 400
        assert "Authorization header is required" in response.text

    async def test_session_create_invalid_category(self):
        user_id = str(uuid4())
        headers = {authorization: user_id}
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/create",
            headers=headers,
            json={"text": "Неверная категория", "category": 99, "choices": [0]},
        )
        assert response.status_code == 400
        assert "Invalid category index" in response.text


def test_sanitize_prompt_text_triggers_condensation(monkeypatch):
    from auto_summarization.services.handlers import session as session_handler

    calls: Dict[str, Any] = {}

    def fake_get_context_window(model_name: str) -> int:
        calls["window"] = model_name
        return 100

    def fake_apply_map_reduce(text: str, context_window: int) -> str:
        calls["map_reduce"] = len(text)
        return "condensed summary"

    monkeypatch.setattr(session_handler, "_get_context_window", fake_get_context_window)
    monkeypatch.setattr(session_handler, "_apply_map_reduce", fake_apply_map_reduce)

    long_text = "А" * 5000
    result = session_handler._sanitize_prompt_text(long_text)

    assert result == "condensed summary"
    assert calls == {"window": session_handler.settings.OPENAI_MODEL_NAME, "map_reduce": len(long_text)}


def test_sanitize_prompt_text_falls_back_to_truncation(monkeypatch):
    from auto_summarization.services.handlers import session as session_handler

    def fake_get_context_window(model_name: str) -> int:
        return 50

    def fake_apply_map_reduce(text: str, context_window: int) -> str:
        return text  # No reduction

    monkeypatch.setattr(session_handler, "_get_context_window", fake_get_context_window)
    monkeypatch.setattr(session_handler, "_apply_map_reduce", fake_apply_map_reduce)

    long_text = "B" * 10000
    result = session_handler._sanitize_prompt_text(long_text)

    # For a context window of 50, safe window will be 512 tokens -> char budget 2048
    assert len(result) <= 2048
    assert result
