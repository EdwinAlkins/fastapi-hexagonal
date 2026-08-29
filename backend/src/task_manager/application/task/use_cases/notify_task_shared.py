"""
Use case : notifie par e-mail les utilisateurs avec qui une tâche est partagée.
"""

from __future__ import annotations

from task_manager.application.shared.errors import EmailSendError
from task_manager.application.shared.html_template.email_template import EmailTemplatePort
from task_manager.application.shared.smtp import NotifyResult, SMTPSenderPort
from task_manager.application.task.dto import ShareTaskNotification
from task_manager.domain.task.repository import TaskRepository
from task_manager.domain.task.value_objects import TaskId
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import UserId


class NotifyTaskShared:
    def __init__(
        self,
        task_repository: TaskRepository,
        user_repository: UserRepository,
        smtp_sender: SMTPSenderPort,
        email_template: EmailTemplatePort,
        from_email: str,
    ):
        self._task_repository = task_repository
        self._user_repository = user_repository
        self._smtp_sender = smtp_sender
        self._email_template = email_template
        self._from_email = from_email

    async def execute(self, notification: ShareTaskNotification) -> NotifyResult:
        task = await self._task_repository.get(TaskId.from_string(notification.task_id))
        owner = await self._user_repository.get(task.owner_id)
        body = self._email_template.render_share_task(
            owner_email=owner.email.value,
            message_body=notification.body,
            task_title=str(task.title),
            task_status=task.status.value,
            task_description=task.description or "—",
            task_created_at=task.created_at.isoformat(),
            task_completed_at=task.completed_at.isoformat() if task.completed_at else "—",
        )
        list_of_unreachable_user_ids: list[str] = []
        for user_id in notification.user_ids:
            user = await self._user_repository.get(UserId.from_string(user_id))
            try:
                await self._smtp_sender.send(
                    to_email=str(user.email),
                    subject=notification.subject,
                    body=body,
                    from_email=self._from_email,
                )
            except EmailSendError:
                list_of_unreachable_user_ids.append(str(user.id))

        return NotifyResult(failed=list_of_unreachable_user_ids)
