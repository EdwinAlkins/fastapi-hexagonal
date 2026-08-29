"""Configuration du logging (application **et** uvicorn).

``logging.basicConfig`` ne suffisait pas : il ne fait rien si le logger racine a
déjà un handler, et il laissait les loggers d'uvicorn avec leur propre format —
deux styles de lignes cohabitaient donc dans la sortie. On passe par un
``dictConfig`` explicite, qui reprend la main sur ``uvicorn`` comme sur
``task_manager`` et produit un format unique.
"""

from __future__ import annotations

from logging.config import dictConfig

FORMAT = "%(asctime)s %(levelname)-5s %(name)-24s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Applique la configuration. À appeler une fois, au démarrage du process."""
    dictConfig(
        {
            "version": 1,
            # Les loggers déjà créés (uvicorn les instancie à l'import) doivent
            # survivre à cette reconfiguration.
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": FORMAT, "datefmt": DATE_FORMAT},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "task_manager": {"level": level, "propagate": True},
                # ``propagate: False`` + handler explicite : sans cela, uvicorn
                # écrit avec son propre format *en plus* du nôtre (doublons).
                "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
                # Journal d'accès d'uvicorn coupé : le middleware de
                # ``presentation.api.middleware`` le remplace en y ajoutant la
                # durée. Les deux actifs donneraient deux lignes par requête.
                "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": False},
            },
        }
    )
