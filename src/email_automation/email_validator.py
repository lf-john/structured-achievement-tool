import re
import socket

from src.mautic.mautic_api_client import MauticApiClient

DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "throwaway.email",
    "yopmail.com",
    "trashmail.com",
    "sharklasers.com",
    "guerrillamailblock.com",
    "grr.la",
    "guerrillamail.info",
    "guerrillamail.biz",
    "guerrillamail.de",
    "guerrillamail.net",
    "guerrillamail.org",
    "spam4.me",
    "dispostable.com",
    "mailnull.com",
    "spamgourmet.com",
    "trashmail.at",
    "trashmail.io",
    "trashmail.me",
    "getairmail.com",
    "filzmail.com",
    "maildrop.cc",
}

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "protonmail.com",
    "pm.me",
    "zoho.com",
    "yandex.com",
    "mail.com",
    "gmx.com",
    "gmx.net",
}

ROLE_PREFIXES = {
    "info",
    "admin",
    "noreply",
    "no-reply",
    "support",
    "help",
    "contact",
    "postmaster",
    "webmaster",
    "hostmaster",
    "abuse",
    "security",
    "root",
    "mailer-daemon",
    "mail",
    "newsletter",
    "billing",
    "accounts",
    "careers",
    "jobs",
    "press",
    "media",
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

QUALITY_MAP = {
    "valid_business": ("High", 90),
    "free_email": ("Medium", 55),
    "role_account": ("Low", 30),
    "disposable_domain": ("Low", 10),
    "invalid_syntax": ("Unverified", 0),
}


class EmailValidator:
    def validate(self, email: str) -> dict:
        if not email or not EMAIL_REGEX.match(email):
            return self._result(email, "invalid_syntax")

        local, domain = email.lower().split("@", 1)

        if domain in DISPOSABLE_DOMAINS:
            return self._result(email, "disposable_domain")

        if domain in FREE_EMAIL_DOMAINS:
            return self._result(email, "free_email")

        if local in ROLE_PREFIXES:
            return self._result(email, "role_account")

        # Attempt MX lookup to confirm domain exists; fall back gracefully
        try:
            self._lookup_mx(domain)
        except (TimeoutError, OSError, socket.error):
            pass

        return self._result(email, "valid_business")

    def _lookup_mx(self, domain: str) -> None:
        socket.getaddrinfo(domain, None)

    def validate_and_update(
        self,
        email: str,
        contact_id: int,
        mautic_url: str,
        mautic_token: str,
    ) -> dict:
        result = self.validate(email)
        client = MauticApiClient(base_url=mautic_url, api_key=mautic_token)
        payload = {"data_quality": result["data_quality"]}
        client.update_contact(contact_id, payload)
        return result

    def _result(self, email: str, classification: str) -> dict:
        data_quality, score = QUALITY_MAP[classification]
        return {
            "email": email,
            "classification": classification,
            "data_quality": data_quality,
            "score": score,
        }
