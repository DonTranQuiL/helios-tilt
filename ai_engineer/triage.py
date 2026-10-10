#!/usr/bin/env python3
"""AI issue triage for Helios Tilt."""
from __future__ import annotations

import os

import requests
from openai import OpenAI

COMPONENT = "custom_components/helios_tilt/"


def _llm_client():
    xai = os.getenv("XAI_API_KEY")
    if xai:
        return OpenAI(base_url="https://api.x.ai/v1", api_key=xai), "grok-4"
    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return (
            OpenAI(base_url="https://openrouter.ai/api/v1", api_key=or_key),
            "deepseek/deepseek-v4.1-flash",
        )
    print("No XAI_API_KEY or OPENROUTER_API_KEY — exiting cleanly.")
    raise SystemExit(0)


issue_title = os.getenv("ISSUE_TITLE", "")
issue_body = os.getenv("ISSUE_BODY", "")
issue_number = os.getenv("ISSUE_NUMBER")
repo = os.getenv("GITHUB_REPOSITORY")
token = os.getenv("GITHUB_TOKEN")

client, model = _llm_client()

prompt = f"""
You are the AI Repository Triage Agent for 'Helios Tilt'
(Home Assistant custom integration at {COMPONENT}).

A user opened:
Title: {issue_title}
Body: {issue_body}

Respond with EXACTLY two lines first:
LABELS: comma-separated github labels (bug, enhancement, question, help wanted, documentation)
COMMENT: a short welcoming technical acknowledgement (no slang in labels).

Then you may add a longer helpful comment body after COMMENT:.
Sign off as: AI Triage Agent for Helios Tilt
"""

try:
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    text = completion.choices[0].message.content or ""
    labels: list[str] = []
    comment = text
    for line in text.splitlines():
        if line.startswith("LABELS:"):
            labels = [
                x.strip()
                for x in line.replace("LABELS:", "", 1).split(",")
                if x.strip()
            ]
        elif line.startswith("COMMENT:"):
            comment = line.replace("COMMENT:", "", 1).strip() or comment

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    if labels and issue_number and repo:
        requests.post(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}/labels",
            headers=headers,
            json={"labels": labels},
            timeout=30,
        )
    if comment and issue_number and repo:
        requests.post(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
            headers=headers,
            json={"body": f"**AI Triage**\n\n{comment}"},
            timeout=30,
        )
except Exception as exc:  # noqa: BLE001
    print(f"Failed triage: {exc}")
