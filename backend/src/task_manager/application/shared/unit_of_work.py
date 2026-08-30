"""Port de pilotage de la transaction, pour les traitements longs.

En temps normal, aucun use case ne committe : la frontière transactionnelle est
tenue par l'adaptateur driving (``get_session`` pour l'API, ``transactional_session``
pour le CLI) et entoure le use case entier. C'est la règle du dépôt, et elle vaut
pour tout ce qui répond à une requête.

Un import en masse est le contre-exemple assumé. Une transaction unique de dix
minutes serait un défaut, pas une garantie :

- avec **PgBouncer en mode transaction**, elle épingle une connexion serveur
  pendant toute sa durée — sur un pool de 20, c'est 5 % de la capacité retirée ;
- le WAL enfle, les lignes mortes s'accumulent ;
- un échec à 99 % perd les 99 %.

On découpe donc en lots, ce qui suppose de committer *pendant* le use case. D'où ce
port : le use case exprime « ce lot est acquis », sans jamais savoir qu'il existe
une session SQLAlchemy derrière. La contrepartie est explicite — l'import n'est pas
atomique — et c'est précisément pour cela qu'il doit être **idempotent** et
reprenable (cf. ``BulkWriteResult``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class UnitOfWorkPort(ABC):
    """Rend durable ce qui a été écrit depuis le dernier point d'acquisition."""

    @abstractmethod
    async def commit(self) -> None:
        """Valide le travail en cours et ouvre implicitement le lot suivant."""
