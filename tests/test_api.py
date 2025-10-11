import os
import re
import shutil
import subprocess
from time import sleep
from uuid import uuid4

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

        files = {"document": ("sample.txt", "Это тестовый документ для проверки загрузки.", "text/plain")}
        response = requests.post(
            f"{self._api_url}{self._prefix}/analysis/load_document",
            headers=self._headers,
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert "документ" in data.get("text").lower()

    async def test_session_create_performs_analysis(self):
        user_id = str(uuid4())
        headers = {authorization: user_id}

        text = "Российский рынок акций вырос на 5%, инвесторы ожидают снижения ставки."
        response = requests.post(
            f"{self._api_url}{self._prefix}/session/create",
            headers=headers,
            json={"text": text, "category": 0, "choices": [0, 3, 4]},
        )
        assert response.status_code == 200
        data = response.json()
        assert re.match(self._id_pattern, data["session_id"])
        assert data["category"] == "Экономика"
        assert "[Универсальная модель]" in data["classifications"]
        assert data["summary"] == data["short_summary"]
        assert data["analysis"] == data["full_summary"]

        sport_text = "Команда одержала победу со счетом 2:1, болельщики были в восторге."
        response = requests.post(
            f"{self._api_url}{self._prefix}/session/create",
            headers=headers,
            json={"text": sport_text, "category": 1, "choices": [1, 3]},
        )
        assert response.status_code == 200
        sport_data = response.json()
        assert "[Предобученная модель]" in sport_data["classifications"]
        assert isinstance(sport_data["entities"], str)

        cleanup = requests.delete(
            f"{self._api_url}{self._prefix}/user/delete_user",
            json={"user_id": user_id},
        )
        assert cleanup.status_code == 200
        assert cleanup.json().get("status") in {"deleted", "not_found"}

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
            f"{self._api_url}{self._prefix}/session/create",
            headers=self._headers,
            json=payload,
        )
        assert response.status_code == 200
        session = response.json()
        session_id = session.get("session_id")
        assert re.match(self._id_pattern, session_id)
        assert session.get("category") == "Путешествия"
        assert session.get("summary") == session.get("short_summary")
        assert session.get("analysis") == session.get("full_summary")

        response = requests.get(
            f"{self._api_url}{self._prefix}/session/fetch_page",
            headers=self._headers,
        )
        assert response.status_code == 200
        sessions = response.json().get("sessions")
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id

        update_payload = {
            "session_id": session_id,
            "summary": "Обновленная аннотация",
            "analysis": "Обновленный подробный вывод",
            "version": session.get("version"),
        }
        response = requests.post(
            f"{self._api_url}{self._prefix}/session/update_summarization",
            headers=self._headers,
            json=update_payload,
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["summary"] == "Обновленная аннотация"
        assert updated["analysis"] == "Обновленный подробный вывод"
        assert updated["version"] == session.get("version") + 1

        response = requests.post(
            f"{self._api_url}{self._prefix}/session/update_title",
            headers=self._headers,
            json={"session_id": session_id, "title": "Новый заголовок", "version": updated["version"]},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Новый заголовок"

        response = requests.delete(
            f"{self._api_url}{self._prefix}/session/delete",
            headers=self._headers,
            json={"session_id": session_id},
        )
        assert response.status_code == 200
        assert response.json().get("status") == "SUCCESS"

        response = requests.get(
            f"{self._api_url}{self._prefix}/session/fetch_page",
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
