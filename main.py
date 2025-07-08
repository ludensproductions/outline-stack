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
        self.api_key = os.getenv("OUTLINE_API_KEY")

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

            comments = result.get("data", [])
            for comment in comments:
                if comment.get("resolvedAt"):  # Check if resolvedAt is not null
                    print(f"{self.base_url}/doc/{comment.get('documentId')}")

            path = result.get("pagination", {}).get("nextPath")

            time.sleep(0.1)

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

        return list(set(docs_urls))

    def save_doc_ids_to_txt(self, file_path: Path, docs_list: list):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for doc_id in docs_list:
                    f.write(f"{doc_id}\n")
            print(f"Saved {len(docs_list)} IDs to {file_path}")
        except Exception as e:
            print(f"Failed to save to TXT: {e}")

if __name__ == "__main__":
    urls_txt = Path(__name__).parent.resolve() / "urls.txt"
    api_client = OutlineAPIClient()
    docs_urls = api_client.fetch_unresolved_comment_doc_ids()
    api_client.save_doc_ids_to_txt(urls_txt, docs_urls)
