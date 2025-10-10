import os
import re
import subprocess
from time import sleep

import pytest
import requests
from conftest import authorization
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.asyncio
class TestAPI:
    def setup_class(self):
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
                    # "--exclude-dir", ".venv", "uv.lock", ".pytest_cache",
                    "--exclude-dir",
                    "tests",
                    "models",
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
        self._api_host = os.environ.get("CHAT_TRANSLATION_API_HOST", "localhost")
        self._api_port = os.environ.get("CHAT_TRANSLATION_API_PORT", 8000)
        self._api_url = f"http://{self._api_host}:{self._api_port}"
        self._prefix = os.environ.get("CHAT_TRANSLATION_URL_PREFIX", "/v1")
        self._headers = {"user_id": None}
        self._users = [
            {"user_id": "d2fb6951-e69f-4402-b3e4-6b73f66b63f5"},
            {"user_id": "d2fb6951-e69f-4402-b3e4-6b73f66b63f6"},
        ]
        self._id_pattern = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"

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

    async def test_docs(self):
        response = requests.get(f"{self._api_url}/docs")
        assert 200 == response.status_code
        assert "FastAPI - Swagger UI" in response.text

    async def test_health(self):
        response = requests.get(f"{self._api_url}/health")
        assert 200 == response.status_code
        assert {"status": "ok"} == response.json()

    async def test_models(self):
        response = requests.get(f"{self._api_url}{self._prefix}/models")
        assert 200 == response.status_code
        data = response.json()
        models = data.get("models")
        assert isinstance(models, list)
        for model in models:
            model_id = model.get("model_id")
            assert re.match(self._id_pattern, model_id)
            assert isinstance(model.get("model_id"), str)
            assert isinstance(model.get("model"), str)
            assert isinstance(model.get("description"), str)
            assert isinstance(model.get("source_language_id"), str)
            assert isinstance(model.get("target_language_id"), str)
            assert isinstance(model.get("source_language_title"), str)
            assert isinstance(model.get("target_language_title"), str)

    async def test_users(self):
        response = requests.get(f"{self._api_url}{self._prefix}/user/get_users")
        assert 200 == response.status_code
        data = response.json()
        users = data.get("users")
        assert isinstance(users, list)
        assert users == []
        payloads = self._users
        for payload in payloads:
            response = requests.post(f"{self._api_url}{self._prefix}/user/create_user", json=payload)
            assert 200 == response.status_code
            data = response.json()
            status = data.get("status")
            assert isinstance(status, str)
            assert "created" == status
        payload = {"user_id": "d2fb6951-e69f-4402-b3e4-6b73f66b63f5"}
        response = requests.post(f"{self._api_url}{self._prefix}/user/create_user", json=payload)
        assert 200 == response.status_code
        data = response.json()
        status = data.get("status")
        assert isinstance(status, str)
        assert "exist" == status
        payload = {"user_id": "temp", "temporary": True}
        response = requests.post(f"{self._api_url}{self._prefix}/user/create_user", json=payload)
        assert 200 == response.status_code
        response = requests.get(f"{self._api_url}{self._prefix}/user/get_users")
        assert 200 == response.status_code
        data = response.json()
        users = data.get("users")
        assert isinstance(users, list)
        assert 3 == len(users)
        for user in users:
            user_id = user.get("user_id")
            assert isinstance(user_id, str)
            temporary = user.get("temporary")
            assert temporary == (True if user_id == "temp" else False)
            started_using_at = user.get("started_using_at")
            assert isinstance(started_using_at, float)
            last_used_at = user.get("last_used_at")
            assert isinstance(last_used_at, float)
            assert last_used_at >= started_using_at
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        assert 3 == len(users)
        assert "temp" in {user.get("user_id") for user in users if user.get('temporary')}
        payload = {"user_id": "temp"}
        response = requests.delete(f"{self._api_url}{self._prefix}/user/delete_user", json=payload)
        assert 200 == response.status_code
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        assert "temp" not in {user.get("user_id") for user in users}
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        assert 2 == len(users)
        payload = {"user_id": users[-1].get("user_id")}
        response = requests.delete(f"{self._api_url}{self._prefix}/user/delete_user", json=payload)
        assert 200 == response.status_code
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        assert 1 == len(users)

    async def test_get_sessions(self):
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        user_id = users[0].get("user_id")
        assert re.match(self._id_pattern, user_id)
        headers = self._headers.copy()
        headers[authorization] = user_id
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        assert 200 == response.status_code
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        assert isinstance(chat_sessions, list)
        assert chat_sessions == []

    async def test_create_session(self):
        assert authorization == "user_id"
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        user_id = users[0].get("user_id")
        assert re.match(self._id_pattern, user_id)
        headers = self._headers.copy()
        headers[authorization] = user_id
        user_id = headers.get("user_id")
        assert re.match(self._id_pattern, user_id)

        models = requests.get(f"{self._api_url}{self._prefix}/models").json().get("models")
        special_model = [
            model for model in models if model["model"] == "SPECIAL" and model["source_language_id"] == "en"
        ][0]
        assert isinstance(special_model, dict)
        payload = {"model_id": special_model.get("model_id"), "query": "Hello world!"}
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/create", headers=headers, json=payload)
        assert 200 == response.status_code

        universal_model = [
            model for model in models if model["model"] == "UNIVERSAL" and model["source_language_id"] == "en"
        ][0]
        assert isinstance(special_model, dict)
        payload = {"model_id": universal_model.get("model_id"), "query": "Hello world!"}
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/create", headers=headers, json=payload)
        assert 200 == response.status_code

        auto_model = [
            model for model in models if model["model"] == "UNIVERSAL" and model["source_language_id"] == "auto"
        ][0]
        assert isinstance(auto_model, dict)
        # best language
        payload = {"model_id": auto_model.get("model_id"), "query": "Hello world!"}
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/create", headers=headers, json=payload)
        assert 200 == response.status_code
        # bad language
        payload = {
            "model_id": auto_model.get("model_id"),
            "query": "El tiempo Hoy hace mucho frío. Es invierno y todas las calles están cubiertas de nieve.",
        }
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/create", headers=headers, json=payload)
        assert 200 == response.status_code
        data = response.json()
        assert isinstance(data.get("error"), str)
        assert data.get("error") == "bad language"
        # auto 1
        payload = {"model_id": None, "query": "Hello world!"}
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/create", headers=headers, json=payload)
        assert 200 == response.status_code
        # auto 2
        payload = {"model_id": "", "query": "Hello world!"}
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/create", headers=headers, json=payload)
        assert 200 == response.status_code
        # bad model
        payload = {"model_id": "bad_model", "query": "Hello world!"}
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/create", headers=headers, json=payload)
        assert 400 == response.status_code
        # results
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        assert isinstance(chat_sessions, list)
        assert 5 == len(chat_sessions)
        for chat_session in chat_sessions:
            assert isinstance(chat_session.get("session_id"), str)
            assert isinstance(chat_session.get("title"), str)
            assert isinstance(chat_session.get("model"), str)
            assert isinstance(chat_session.get("query"), str)
            assert isinstance(chat_session.get("translation"), str)
            assert isinstance(chat_session.get("source_language_id"), str)
            assert isinstance(chat_session.get("target_language_id"), str)
            assert isinstance(chat_session.get("source_language_title"), str)
            assert isinstance(chat_session.get("target_language_title"), str)
            assert isinstance(chat_session.get("version"), int)
            assert isinstance(chat_session.get("inserted_at"), float)
            assert isinstance(chat_session.get("updated_at"), float)
            assert isinstance(chat_session.get("error"), str | None)
            assert chat_session.get("updated_at") >= chat_session.get("inserted_at")
            assert chat_session.get("model") in ["UNIVERSAL", "SPECIAL"]

    async def test_update_translation_session(self):
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        user_id = users[0].get("user_id")
        headers = self._headers.copy()
        headers[authorization] = user_id
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        assert 200 == response.status_code
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        chat_session = chat_sessions[0]
        start_title = chat_session.get("title")
        models = requests.get(f"{self._api_url}{self._prefix}/models").json().get("models")
        auto_model = [
            model for model in models if model["model"] == "UNIVERSAL" and model["source_language_id"] == "auto"
        ][0]
        # best language
        session_id = chat_session.get("session_id")
        model_id = auto_model.get("model_id")
        version = chat_session.get("version")
        updated_at = chat_session.get("updated_at")
        query = chat_session.get("query")
        translation = chat_session.get("translation")
        payload = {
            "session_id": session_id,
            "model_id": model_id,
            "query": "Hello world 2!",
            "version": version,
        }
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_translation", headers=headers, json=payload
        )
        assert 200 == response.status_code
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        assert isinstance(chat_sessions, list)
        assert 5 == len(chat_sessions)
        session = [session for session in chat_sessions if session.get("session_id") == session_id][0]
        assert isinstance(session.get("session_id"), str)
        assert isinstance(session.get("title"), str)
        assert isinstance(session.get("model"), str)
        assert isinstance(session.get("query"), str)
        assert isinstance(session.get("translation"), str)
        assert isinstance(session.get("source_language_id"), str)
        assert isinstance(session.get("target_language_id"), str)
        assert isinstance(session.get("source_language_title"), str)
        assert isinstance(session.get("target_language_title"), str)
        assert isinstance(session.get("version"), int)
        assert isinstance(session.get("inserted_at"), float)
        assert isinstance(session.get("updated_at"), float)
        assert session.get("error") is None
        assert session_id == session.get("session_id")
        assert (version + 1) == session.get("version")
        assert start_title == session.get("title")
        assert "UNIVERSAL" == session.get("model")
        assert session.get("updated_at") > updated_at
        assert query != session.get("query")
        assert payload["query"] == session.get("query")
        assert translation != session.get("translation")
        # bed language
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        assert 200 == response.status_code
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        chat_session = chat_sessions[0]
        session_id = chat_session.get("session_id")
        model_id = auto_model.get("model_id")
        version = chat_session.get("version")
        translation = chat_session.get("translation")
        payload = {
            "session_id": session_id,
            "model_id": model_id,
            "query": "El tiempo Hoy hace mucho frío. Es invierno y todas las calles están cubiertas de nieve.",
            "version": version,
        }
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_translation", headers=headers, json=payload
        )
        assert 200 == response.status_code
        data = response.json()
        assert isinstance(data.get("session_id"), str)
        assert isinstance(data.get("title"), str)
        assert isinstance(data.get("model"), str)
        assert isinstance(data.get("query"), str)
        assert isinstance(data.get("translation"), str)
        assert isinstance(data.get("source_language_title"), str)
        assert isinstance(data.get("target_language_title"), str)
        assert isinstance(data.get("version"), int)
        assert isinstance(data.get("inserted_at"), float)
        assert isinstance(data.get("updated_at"), float)
        assert isinstance(data.get("error"), str)
        assert "bad language" == data.get("error")
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        assert isinstance(chat_sessions, list)
        assert 5 == len(chat_sessions)
        session = [session for session in chat_sessions if session.get("session_id") == session_id][0]
        assert chat_session.get("session_id") == session.get("session_id")
        assert version == session.get("version")
        assert chat_session.get("title") == session.get("title")
        assert chat_session.get("model") == session.get("model")
        assert chat_session.get("updated_at") == session.get("updated_at")
        assert chat_session.get("query") == session.get("query")
        assert payload["query"] != session.get("query")
        assert translation == session.get("translation")

    async def test_update_title(self):
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        user_id = users[0].get("user_id")
        headers = self._headers.copy()
        headers[authorization] = user_id
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        assert 200 == response.status_code
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        chat_session = chat_sessions[0]
        session_id = chat_session.get("session_id")
        version = chat_session.get("version")
        payload = {
            "session_id": session_id,
            "title": "New title",
            "version": version,
        }
        response = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_title", headers=headers, json=payload
        )
        assert 200 == response.status_code
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        assert isinstance(chat_sessions, list)
        assert 5 == len(chat_sessions)
        session = [session for session in chat_sessions if session.get("session_id") == session_id][0]
        assert isinstance(session.get("session_id"), str)
        assert isinstance(session.get("title"), str)
        assert (version + 1) == session.get("version")
        assert "New title" == session.get("title")

    async def test_download_translation(self):
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        user_id = users[0].get("user_id")
        headers = self._headers.copy()
        headers[authorization] = user_id
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        chat_session = chat_sessions[0]
        session_id = chat_session.get("session_id")
        payload = {
            "session_id": session_id,
            "format": "pdf",
        }
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/download/{session_id}/pdf", headers=headers, json=payload)
        assert 200 == response.status_code

    async def test_search(self):
        # подготовка
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        assert isinstance(users, list) and len(users) >= 1
        user_id = users[0].get("user_id")
        assert re.match(self._id_pattern, user_id)
        headers = self._headers.copy()
        headers[authorization] = user_id

        # убеждаемся, что есть сессии
        resp = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        assert resp.status_code == 200
        sessions = resp.json().get("chat_sessions")
        assert isinstance(sessions, list)

        # успешный поиск
        payload = {"query": "Hello"}
        response = requests.post(f"{self._api_url}{self._prefix}/chat_session/search", headers=headers, json=payload)
        assert 200 == response.status_code
        data = response.json()
        assert isinstance(data, dict)
        sessions = data.get("sessions")
        assert isinstance(sessions, list)
        assert len(sessions) > 0

        # проверки структуры результатов
        prev_score = 1.0
        for session in sessions:
            assert isinstance(session.get("title"), str)
            assert isinstance(session.get("query"), str)
            assert isinstance(session.get("translation"), str)
            assert isinstance(session.get("inserted_at"), float)
            assert isinstance(session.get("score"), float)
            assert 0.0 < session.get("score") <= 1.0
            assert re.match(self._id_pattern, session.get("session_id"))
            assert session.get("score") <= prev_score
            prev_score = session.get("score")

        # пустой запрос -> 400
        bad_payload = {"query": ""}
        bad_resp = requests.post(f"{self._api_url}{self._prefix}/chat_session/search", headers=headers, json=bad_payload)
        assert 400 == bad_resp.status_code
        err = bad_resp.json()
        assert isinstance(err.get("detail"), str)

    async def test_delete_session(self):
        users = requests.get(f"{self._api_url}{self._prefix}/user/get_users").json().get("users")
        user_id = users[0].get("user_id")
        headers = self._headers.copy()
        headers[authorization] = user_id
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        assert 200 == response.status_code
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        chat_session = chat_sessions[0]
        payload = {"session_id": chat_session.get("session_id")}
        start_len = len(chat_sessions)
        response = requests.delete(f"{self._api_url}{self._prefix}/chat_session/delete", headers=headers, json=payload)
        assert 200 == response.status_code
        response = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=headers)
        data = response.json()
        chat_sessions = data.get("chat_sessions")
        assert (start_len - 1) == len(chat_sessions)
