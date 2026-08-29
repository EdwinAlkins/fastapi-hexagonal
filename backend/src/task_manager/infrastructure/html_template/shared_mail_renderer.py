"""Adaptateur pour le rendu du template de mail de partage de tâche."""

from __future__ import annotations

from html import escape
from pathlib import Path

from task_manager.application.shared.html_template.email_template import EmailTemplatePort


class ShareTaskMailTemplateAdapter(EmailTemplatePort):
    def __init__(self, templates_dir: Path = Path(__file__).parent / "templates"):
        self._share_task = (templates_dir / "share_task.html").read_text(encoding="utf-8")

    def render_share_task(self, **kwargs: str) -> str:
        return self._share_task.format(**{k: escape(str(v)) for k, v in kwargs.items()})
