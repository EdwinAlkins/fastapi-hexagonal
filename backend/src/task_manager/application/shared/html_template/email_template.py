"""
EmailTemplatePort is an abstract class that defines the interface for rendering email templates.
"""

from abc import ABC, abstractmethod


class EmailTemplatePort(ABC):
    """
    EmailTemplatePort is an abstract class that defines the interface for rendering email templates.
    """

    @abstractmethod
    def render_share_task(
        self,
        *,
        owner_email: str,
        message_body: str,
        task_title: str,
        task_status: str,
        task_description: str,
        task_created_at: str,
        task_completed_at: str,
    ) -> str: ...
