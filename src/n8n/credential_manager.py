import requests


class N8NCredentialError(Exception):
    pass


class N8NCredentialManager:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Connectivity checks
    # ------------------------------------------------------------------

    def verify_apollo_connectivity(self, api_key: str) -> bool:
        if not api_key:
            return False
        try:
            url = "https://api.apollo.io/v1/auth/health"
            resp = requests.get(url, headers={"X-Api-Key": api_key}, timeout=10)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def verify_ipinfo_connectivity(self, token: str) -> bool:
        if not token:
            return False
        try:
            url = f"https://ipinfo.io/1.1.1.1?token={token}"
            resp = requests.get(url, timeout=10)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def verify_apify_connectivity(self, api_token: str) -> bool:
        if not api_token:
            return False
        try:
            url = f"https://api.apify.com/v2/users/me?token={api_token}"
            resp = requests.get(url, timeout=10)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def verify_mautic_connectivity(self, api_url: str, username: str, password: str) -> bool:
        try:
            url = f"{api_url.rstrip('/')}/api/users/self"
            resp = requests.get(url, auth=(username, password), timeout=10)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def verify_all_credentials(self, credential_map: dict) -> dict:
        result = {}
        for service, creds in credential_map.items():
            if service == "apollo":
                result["apollo"] = self.verify_apollo_connectivity(creds.get("api_key", ""))
            elif service == "ipinfo":
                result["ipinfo"] = self.verify_ipinfo_connectivity(creds.get("token", ""))
            elif service == "apify":
                result["apify"] = self.verify_apify_connectivity(creds.get("api_token", ""))
            elif service == "mautic":
                result["mautic"] = self.verify_mautic_connectivity(
                    creds.get("api_url", ""),
                    creds.get("username", ""),
                    creds.get("password", ""),
                )
            else:
                result[service] = False
        return result

    # ------------------------------------------------------------------
    # Credential creation (POST to N8N)
    # ------------------------------------------------------------------

    def _create_credential(self, name: str, credential_type: str, data: dict) -> str:
        url = f"{self.api_url}/credentials"
        payload = {"name": name, "type": credential_type, "data": data}
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()["id"]
        except requests.exceptions.HTTPError as exc:
            raise N8NCredentialError(f"Failed to create credential '{name}': {exc}") from exc

    def create_apollo_credential(self, api_key: str) -> str:
        return self._create_credential("Apollo API", "apolloApi", {"apiKey": api_key})

    def create_ipinfo_credential(self, token: str) -> str:
        return self._create_credential("IPinfo Token", "ipinfoApi", {"token": token})

    def create_apify_credential(self, api_token: str) -> str:
        return self._create_credential("Apify Token", "apifyApi", {"token": api_token})

    def create_mautic_credential(self, api_url: str, username: str, password: str) -> str:
        return self._create_credential(
            "Mautic API",
            "mauticApi",
            {"url": api_url, "username": username, "password": password},
        )

    # ------------------------------------------------------------------
    # Workflow utilities
    # ------------------------------------------------------------------

    def replace_workflow_placeholders(self, workflow_id: str, placeholders: dict) -> dict:
        url = f"{self.api_url}/workflows/{workflow_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise N8NCredentialError(
                f"Failed to fetch workflow '{workflow_id}': {exc}"
            ) from exc
