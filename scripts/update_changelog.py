#!/usr/bin/env python3
"""Update CHANGELOG.md for a new release."""

import re
import sys
from datetime import date
from pathlib import Path


def update_changelog(version: str, tag: str, repository: str) -> None:
    """
    Update CHANGELOG.md by moving Unreleased content to a new version section.

    Args:
        version: Version number (e.g., "0.1.0")
        tag: Git tag (e.g., "v0.1.0")
        repository: GitHub repository (e.g., "owner/repo")
    """
    changelog_path = Path("CHANGELOG.md")

    if not changelog_path.exists():
        print("CHANGELOG.md not found, creating it")
        changelog_path.write_text(
            """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

"""
        )

    content = changelog_path.read_text()

    # Extract Unreleased section content (everything after ## [Unreleased] until next version or end)
    unreleased_pattern = (
        r"## \[Unreleased\]\s*\n(.*?)(?=\n## \[[\d.]|\[Unreleased\]:|\Z)"
    )
    unreleased_match = re.search(unreleased_pattern, content, re.DOTALL)
    unreleased_content = unreleased_match.group(1).strip() if unreleased_match else ""

    # Extract existing version sections (everything from first version until links section)
    versions_section_match = re.search(
        r"(## \[[\d.]+.*?)(?=\n\[Unreleased\]:|\Z)", content, re.DOTALL
    )
    existing_versions = (
        versions_section_match.group(1).strip() if versions_section_match else ""
    )

    # Extract existing links section
    links_match = re.search(r"(\[Unreleased\]:.*)", content, re.DOTALL)
    existing_links = links_match.group(1).strip() if links_match else ""

    # Get previous version for comparison link
    prev_version_match = re.search(r"^## \[([\d.]+)\]", existing_versions, re.MULTILINE)
    prev_version = prev_version_match.group(1) if prev_version_match else None

    # Build new changelog
    today = date.today().isoformat()

    # Format unreleased content with proper indentation if it exists
    if unreleased_content:
        formatted_unreleased = f"{unreleased_content}\n"
    else:
        formatted_unreleased = ""

    new_version_section = f"## [{version}] - {today}\n{formatted_unreleased}"

    # Build the new content
    new_content = f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

{new_version_section}"""

    # Add existing versions if any
    if existing_versions:
        new_content += f"{existing_versions}\n\n"

    # Add links section
    new_content += (
        f"[Unreleased]: https://github.com/{repository}/compare/{tag}...HEAD\n"
    )

    # Add version link
    if prev_version:
        new_content += f"[{version}]: https://github.com/{repository}/compare/v{prev_version}...{tag}\n"
    else:
        new_content += (
            f"[{version}]: https://github.com/{repository}/releases/tag/{tag}\n"
        )

    # Add remaining links (skip Unreleased link which we already added)
    if existing_links:
        remaining_links = "\n".join(
            line
            for line in existing_links.split("\n")
            if line.strip() and not line.startswith("[Unreleased]:")
        )
        if remaining_links:
            new_content += remaining_links + "\n"

    changelog_path.write_text(new_content)
    print(f"Updated CHANGELOG.md for version {version}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: update_changelog.py <version> <tag> <repository>")
        sys.exit(1)

    update_changelog(sys.argv[1], sys.argv[2], sys.argv[3])
