"""Use case : renommer un utilisateur (avec invalidation du cache)."""

from __future__ import annotations

from task_manager.application.shared.cache import CachePort
from task_manager.application.user.dto import UserDTO
from task_manager.domain.user.repository import UserRepository
from task_manager.domain.user.value_objects import UserId, UserName


class RenameUser:
    """Renomme un utilisateur, puis invalide son entrée de cache.

    Contrepartie de ``GetUser`` : toute mutation d'un agrégat mis en cache doit
    invalider la clé correspondante (``user:{id}``), sinon les lectures
    serviraient l'ancienne valeur jusqu'à expiration du TTL. L'invalidation est
    la responsabilité du use case de mutation — c'est lui qui sait qu'une donnée
    cachée vient de changer.
    """

    def __init__(self, repository: UserRepository, cache: CachePort) -> None:
        self._repository = repository
        self._cache = cache

    async def execute(self, user_id: str, new_name: str) -> UserDTO:
        identity = UserId.from_string(user_id)
        user = await self._repository.get(identity)
        user.rename(UserName(new_name))
        await self._repository.save(user)
        # Invalidation cache-aside : la clé sera reconstruite au prochain GetUser
        # (miss → lecture base → réécriture). Simple et sans risque de servir du périmé.
        await self._cache.delete(f"user:{identity}")
        return UserDTO.from_entity(user)
