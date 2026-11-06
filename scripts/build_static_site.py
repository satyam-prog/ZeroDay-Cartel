#!/usr/bin/env python3
"""Build an allowlisted, public-only site bundle for Render Static Sites."""

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
PUBLIC_FILES = (
    "index.html",
    "login.html",
    "account.html",
    "share-food.html",
    "find-food.html",
    "volunteer.html",
    "privacy.html",
    "terms.html",
    "favicon.svg",
    "assets/images/foodbridge-illustration.svg",
    "assets/css/tailwind.css",
    "assets/css/styles.css",
    "assets/js/icons.js",
    "assets/js/main.js",
    "assets/js/login.js",
    "assets/js/firebase-config.js",
    "assets/js/firebase-client.js",
    "assets/js/account-nav.js",
    "assets/js/page-auth.js",
    "assets/js/account.js",
    "assets/js/share-food.js",
    "assets/js/find-food.js",
    "assets/js/volunteer.js",
)


def build() -> None:
    if OUTPUT.exists():
        if OUTPUT.resolve().parent != ROOT.resolve():
            raise RuntimeError("Refusing to clean output outside the project root.")
        shutil.rmtree(OUTPUT)

    for relative_path in PUBLIC_FILES:
        source = ROOT / relative_path
        if not source.is_file():
            raise FileNotFoundError(f"Required public site file is missing: {relative_path}")
        destination = OUTPUT / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    forbidden_paths = ("dashboard.html", "services", "database", "temp_storage", "certs")
    for path in forbidden_paths:
        if (OUTPUT / path).exists():
            raise RuntimeError(f"Non-public content was included in the site bundle: {path}")

    print(f"Built public-only static site in {OUTPUT}")


if __name__ == "__main__":
    build()
