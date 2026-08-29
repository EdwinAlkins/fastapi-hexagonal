"""Use case : créer un utilisateur."""

from __future__ import annotations

from task_manager.application.user.dto import CreateUserCommand, UserDTO
from task_manager.domain.user.entities import User
from task_manager.domain.user.exceptions import EmailAlreadyUsed
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import Email, UserName


class CreateUser:
    """Orchestre la création d'un utilisateur en garantissant l'unicité de l'e-mail."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def execute(self, command: CreateUserCommand) -> UserDTO:
        email = Email(command.email)
        if await self._repository.find_by_email(email) is not None:
            raise EmailAlreadyUsed(str(email))

        user = User.create(name=UserName(command.name), email=email)
        await self._repository.save(user)
        return UserDTO.from_entity(user)
