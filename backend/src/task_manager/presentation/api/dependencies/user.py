"""Câblage des use cases du bounded context ``user``."""

from __future__ import annotations

from task_manager.application.user.use_cases.create_user import CreateUser
from task_manager.application.user.use_cases.get_user import GetUser
from task_manager.application.user.use_cases.list_users import ListUsers
from task_manager.application.user.use_cases.rename_user import RenameUser
from task_manager.presentation.api.dependencies.cache import CachePortDep
from task_manager.presentation.api.dependencies.repositories import UserRepositoryDep


def get_create_user(users: UserRepositoryDep) -> CreateUser:
    return CreateUser(users)


def get_get_user(users: UserRepositoryDep, cache: CachePortDep) -> GetUser:
    return GetUser(users, cache)


def get_rename_user(users: UserRepositoryDep, cache: CachePortDep) -> RenameUser:
    return RenameUser(users, cache)


def get_list_users(users: UserRepositoryDep) -> ListUsers:
    return ListUsers(users)
