import os
import subprocess
from time import sleep

import pytest
import requests
from dotenv import load_dotenv

from tests.conftest import authorization as auth_header

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
        with open(self._content_file_path, "w", encoding="utf-8") as content_file:
            content_file.write("**Logs**\n\n")
        with open(self._content_file_path, "a", encoding="utf-8") as content_file:
            subprocess.run(
                ["docker", "compose", "-f", self._compose_file, "up", "--build", "-d"],
                stdout=content_file,
                stderr=content_file,
            )
        with open(self._content_file_path, "a", encoding="utf-8") as content_file:
            subprocess.run(
                [
                    "printdirtree",
                    "--exclude-dir",
                    "tests",
                    "huggingface",
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
        self._user_headers = {auth_header: "tester"}
        self._sample_text = (
            "Компания ООО \"ТехИнвест\" заключила контракт с Иваном Ивановым в Москве. "
            "Телефон +7 999 123-45-67 и почта ivan@example.com используются для связи. "
            "Сайт https://techinvest.ru и аккаунт @techinvest помогают поддерживать контакт. "
            "Сделка принесла прибыль и обеспечила устойчивый рост."
        )

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
                    with open(self._content_file_path, "a", encoding="utf-8") as content_file:
                        subprocess.run(
                            ["docker", "compose", "-f", self._compose_file, "logs"],
                            cwd=self._cwd,
                            stdout=content_file,
                            stderr=content_file,
                        )
                    subprocess.run(
                        ["docker", "compose", "-f", self._compose_file, "down", "-v"],
                        cwd=self._cwd,
                        stdout=open(os.devnull, "w", encoding="utf-8"),
                        stderr=subprocess.STDOUT,
                    )
                    raise Exception("Setup timeout")

    def teardown_class(self):
        with open(self._content_file_path, "a", encoding="utf-8") as content_file:
            content_file.write("\n\n**Logs:**\n\n")
        with open(self._content_file_path, "a", encoding="utf-8") as content_file:
            subprocess.run(
                ["docker", "compose", "-f", self._compose_file, "logs"],
                cwd=self._cwd,
                stdout=content_file,
                stderr=content_file,
            )
        subprocess.run(
            ["docker", "compose", "-f", self._compose_file, "down", "-v"],
            cwd=self._cwd,
            stdout=open(os.devnull, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

    async def test_docs(self):
        response = requests.get(f"{self._api_url}/docs")
        assert response.status_code == 200
        assert "Swagger UI" in response.text

    async def test_health(self):
        response = requests.get(f"{self._api_url}/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_analyze_types(self):
        response = requests.get(f"{self._api_url}{self._prefix}/analyze_types")
        assert response.status_code == 200
        data = response.json()
        assert data["categories"] == ["Экономика", "Спорт", "Путешествия"]
        assert data["choices"] == ["Аннотация", "Объекты", "Тональность", "Классификация", "Выводы"]

    async def test_load_document(self):
        files = {"document": ("sample.txt", self._sample_text, "text/plain")}
        response = requests.post(f"{self._api_url}{self._prefix}/load_document", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["text"].startswith("Компания ООО \"ТехИнвест\"")

    async def test_analyze(self):
        payload = {"text": self._sample_text, "category": 0, "choices": [0, 1, 2, 3, 4]}
        response = requests.post(f"{self._api_url}{self._prefix}/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()

        entities = data.get("entities")
        assert "Иван Иванов" in entities.get("persons", [])
        assert any("ООО" in org for org in entities.get("organizations", []))
        assert entities.get("phones") and "+7" in entities["phones"][0]
        assert "ivan@example.com" in entities.get("emails", [])
        assert any(url.startswith("https://") for url in entities.get("urls", []))
        assert "@techinvest" in entities.get("social_accounts", [])

        sentiments = data.get("sentiments")
        assert sentiments.get("polarity") == "positive"
        assert sentiments.get("toxicity", {}).get("has_toxic") is False

        classifications = data.get("classifications")
        assert classifications.get("category") == "Экономика"
        assert classifications.get("model_type") == "universal"

        short_summary = data.get("short_summary")
        full_summary = data.get("full_summary")
        assert isinstance(short_summary, str) and len(short_summary) > 0
        assert isinstance(full_summary, str) and len(full_summary) > 0

    async def test_analyze_validation(self):
        payload = {"text": " ", "category": 0, "choices": [0]}
        response = requests.post(f"{self._api_url}{self._prefix}/analyze", json=payload)
        assert response.status_code == 400
        assert isinstance(response.json().get("detail"), str)

    async def test_sessions_crud(self):
        payload = {
            "text": self._sample_text,
            "category": 0,
            "choices": [0, 1, 2, 3, 4],
            "title": "Первая сессия",
        }
        create = requests.post(
            f"{self._api_url}{self._prefix}/sessions",
            json=payload,
            headers=self._user_headers,
        )
        assert create.status_code == 200
        created = create.json()
        session_id = created["session_id"]

        listing = requests.get(
            f"{self._api_url}{self._prefix}/sessions",
            headers=self._user_headers,
        )
        assert listing.status_code == 200
        listed_ids = [item["session_id"] for item in listing.json()["sessions"]]
        assert session_id in listed_ids

        detail = requests.get(
            f"{self._api_url}{self._prefix}/sessions/{session_id}",
            headers=self._user_headers,
        )
        assert detail.status_code == 200
        detail_json = detail.json()
        assert detail_json["analysis"]["entities"]

        update_payload = {
            "title": "Обновленная сессия",
            "version": detail_json["version"],
        }
        update = requests.patch(
            f"{self._api_url}{self._prefix}/sessions/{session_id}",
            json=update_payload,
            headers=self._user_headers,
        )
        assert update.status_code == 200
        update_json = update.json()
        assert update_json["title"] == "Обновленная сессия"
        assert update_json["version"] == detail_json["version"] + 1

        delete = requests.delete(
            f"{self._api_url}{self._prefix}/sessions/{session_id}",
            headers=self._user_headers,
        )
        assert delete.status_code == 200
        assert delete.json() == {"status": "deleted"}

        missing = requests.get(
            f"{self._api_url}{self._prefix}/sessions/{session_id}",
            headers=self._user_headers,
        )
        assert missing.status_code == 404
