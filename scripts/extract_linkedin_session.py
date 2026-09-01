"""Local interactive CLI utility to extract and encrypt LinkedIn Playwright session state.

Run locally on an operator workstation:
    uv run python scripts/extract_linkedin_session.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from agent.browser.session import encrypt_storage_state, generate_encryption_key


async def extract_session(
    output_path: Path | None = None, key_str: str | None = None
) -> tuple[str, str]:
    """Launch interactive browser, wait for login, and encrypt storage state."""
    key = key_str or os.environ.get("SESSION_ENCRYPTION_KEY") or generate_encryption_key()

    print("=" * 60)
    print("LINKEDIN SESSION EXTRACTOR")
    print("=" * 60)
    print("A browser window will open.")
    print("Please log into your LinkedIn account and complete any 2FA/challenges.")
    print("=" * 60)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        print("Waiting for login completion (monitoring for 'li_at' cookie)...")
        authenticated = False
        for _ in range(120):  # 2 minute timeout
            await asyncio.sleep(1)
            cookies = await context.cookies()
            if any(c["name"] == "li_at" and "linkedin.com" in c["domain"] for c in cookies):
                authenticated = True
                break

        if not authenticated:
            await browser.close()
            raise RuntimeError("Authentication timed out or 'li_at' cookie was not found.")

        print("Login detected! Capturing storage state...")
        temp_state_file = Path("temp_storage_state.json")
        await context.storage_state(path=str(temp_state_file))
        await browser.close()

        raw_bytes = temp_state_file.read_bytes()
        temp_state_file.unlink(missing_ok=True)

        # Save local storage state for immediate local workstation use
        local_storage_file = Path("storage_state.json")
        local_storage_file.write_bytes(raw_bytes)

        encrypted_token = encrypt_storage_state(raw_bytes, key)

        if output_path:
            output_path.write_text(encrypted_token, encoding="utf-8")
            print(f"Encrypted session state written to: {output_path}")

        print("=" * 60)
        print("EXTRACTION SUCCESSFUL!")
        print("=" * 60)
        print("1. Local session written to: storage_state.json (ready for local dry runs)")
        print("2. Save these secrets in GitHub Secrets / .env:")
        print(f"SESSION_ENCRYPTION_KEY={key}")
        print(f"LINKEDIN_SESSION_STATE_ENC={encrypted_token}")
        print("=" * 60)

        return key, encrypted_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and encrypt LinkedIn session state")
    parser.add_argument(
        "--out", type=Path, default=None, help="Optional output path for encrypted token"
    )
    parser.add_argument("--key", type=str, default=None, help="Optional Fernet encryption key")
    args = parser.parse_args()

    try:
        asyncio.run(extract_session(output_path=args.out, key_str=args.key))
        sys.exit(0)
    except Exception as err:
        print(f"Extraction failed: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
