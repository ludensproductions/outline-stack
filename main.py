import os
import requests
import json
import time
from urllib.parse import urljoin
from pathlib import Path


from dotenv import load_dotenv


load_dotenv()


class OutlineAPIClient:
    def __init__(self):
        self.base_url = os.getenv("OUTLINE_URL")
        self.disord_notification_url = os.getenv("DISCORD_NOTIFICATION_URL")
        self.api_key = os.getenv("OUTLINE_API_KEY")
        self.docs_urls = None
        self.target_notification_id = os.getenv("TARGET_NOTIFICATION_ID")
        self.formatted_urls = dict()

    def _generate_headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _generate_body(self, data: dict):
        if not data:
            return None
        return json.dumps(data)

    def post(self, endpoint: str, data: dict = None):
        url = urljoin(self.base_url, endpoint)
        print(f"Calling URL: {url}")
        headers = self._generate_headers()
        body = self._generate_body(data)

        try:
            response = requests.post(url, headers=headers, data=body)
            response.raise_for_status()
            print(f"    URL responded with: {response.status_code}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"    Request failed: {e}")
            return None

    def get(self, endpoint: str, params: dict = None):
        url = f"{self.base_url}{endpoint}"
        headers = self._generate_headers()

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None

    def fetch_resolved_comment_doc_ids(self):
        """Not finished
        """
        path = "/api/comments.list"

        while path:
            result = self.post(endpoint=path)

            comments = result.get("data", []) if result else None
            for comment in comments:
                if comment.get("resolvedAt"):  # Check if resolvedAt is not null
                    print(f"{self.base_url}/doc/{comment.get('documentId')}")

            path = result.get("pagination", {}).get("nextPath")

            time.sleep(0.1)

    def fetch_document_info(self, document_id: str):
        path = "/api/documents.info"
        result = self.post(endpoint=path, data={"id": document_id})
        return result

    def fetch_unresolved_comment_doc_ids(self):
        path = "/api/comments.list"

        docs_urls = []

        while path:
            result = self.post(endpoint=path)

            comments = result.get("data", [])
            if not comments:
                break

            for comment in comments:
                if not comment.get("resolvedAt") and not comment.get("parentCommentId"):
                    docs_urls.append(f"{self.base_url}/doc/{comment.get('documentId')}")

            path = result.get("pagination", {}).get("nextPath")

            time.sleep(0.1)

        self.docs_urls = list(set(docs_urls))
        return self.docs_urls

    def map_id_title(self):
        title_url_map = dict()
        for doc_url in self.docs_urls:
            doc_url: str
            doc_id = doc_url.rsplit("/", maxsplit=1)[-1]

            document_data = self.fetch_document_info(document_id=doc_id)
            document_title = document_data.get("data", {}).get("title", {})
            title_url_map.update({
                document_title: f"[{document_title}]({doc_url})"
            })

        self.formatted_urls = dict(sorted(title_url_map.items()))

    def save_doc_ids_to_txt(self, file_path: Path, docs_list: list):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for doc_id in docs_list:
                    f.write(f"{doc_id}\n")
            print(f"Saved {len(docs_list)} IDs to {file_path}")
        except Exception as e:
            print(f"Failed to save to TXT: {e}")

    def get_webhook_data(self):
        headers = {
            "Content-Type": "application/json"
        }
        files = {}

        webhook_data = {
            "url": self.disord_notification_url,
            "files": files,
            "headers": headers
        }
        return webhook_data

    def send_message_to_webhook(
        self,
        content,
        embed_title,
        embed_description="",
        embed_color=0x00FF00
    ):
        webhook_data = self.get_webhook_data()
        payload = {
            "content": content,
            "embeds": [
                {
                    "title": embed_title,
                    "description": embed_description,
                    "color": embed_color
                }
            ]
        }

        response = requests.post(
            webhook_data["url"],
            headers=webhook_data["headers"],
            data=json.dumps(payload),
            files=webhook_data["files"]
        )

        print(f"Webhook status code: {response.status_code}")
        try:
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"    Webhook request failed: {e}")

    def format_doc_ids_as_markdown(self):
        markdown_list = "\n".join(f"{idx}. {doc_id}" for idx, (_, doc_id) in enumerate(self.formatted_urls.items(), start=1))
        return markdown_list

if __name__ == "__main__":
    # urls_txt = Path(__name__).parent.resolve() / "urls.txt"
    api_client = OutlineAPIClient()

    api_client.fetch_unresolved_comment_doc_ids()
    if api_client.docs_urls:
        api_client.map_id_title()
        api_client.send_message_to_webhook(
            f"<@&{api_client.target_notification_id}>",
            "**Documents with unresolved comments**",
            api_client.format_doc_ids_as_markdown(),
        )
