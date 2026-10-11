"""
Modelos de las tablas `challenges` y `challenge_instances`.

`challenges` es el catálogo de retos. Reemplaza a `challengeRegistry` del
prototipo Node (`wispr_terminal_professional/server.js` +
`challenge-engine.js`), donde el catálogo vivía en memoria y se perdía al
reiniciar. Guarda tanto los retos Wi-Fi hechos a mano del prototipo
(`generator="curriculum"`) como los del pipeline de IA de este backend
(`generator="ai"`, ver docs/pipeline_ia_retos.md) — una sola tabla para
los dos orígenes, así el frontend no tiene que distinguirlos.

`challenge_instances` guarda la flag PERSONAL de cada (jugador, reto): en
el prototipo cada estudiante recibe su propia copia del archivo con una
flag distinta, para que no pueda pasársela a un compañero. Decisión del
11 oct: la tabla se crea ya (para no necesitar otra migración después),
pero mientras no se migre la generación de archivos por jugador
(`challenge-instances.js`) queda vacía y se valida contra `Challenge.flag`
— exactamente el respaldo que ya usa el prototipo
(`getInstanceFlag(...) || challenge.flag`).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Challenge(Base):
    __tablename__ = "challenges"

    # Id legible tipo "wpa-handshake-foundation" (no un número): es el mismo
    # id que ya usa el frontend en sus URLs y en `player.solved`.
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(90), nullable=False)
    # Texto libre que muestra el frontend ("WPA/WPA2", "Deauth / DoS", "crypto").
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    # Clase de ataque que decide cómo se arma el archivo del reto: en el
    # prototipo es `kind` ("wpa-handshake", "pmkid", "deauth"); en el
    # pipeline de IA es `technique` ("iv_reuse_wep", "xor_singlebyte").
    kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # "Foundation" | "Medium" | "Hard" | "Expert" — vocabulario del frontend.
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Flag del catálogo. NUNCA sale en una respuesta de la API: ver
    # `public_challenge()` en app/services/challenges.py.
    flag: Mapped[str] = mapped_column(String(200), nullable=False)
    # Solución completa (viene del ChallengeSpec de la IA). Material para el
    # docente; tampoco se expone a estudiantes.
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Listas cortas que el frontend muestra tal cual. Se guardan como JSON en
    # vez de tablas aparte porque nunca se buscan ni se filtran por dentro:
    # normalizarlas sería complejidad sin beneficio.
    tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    hints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{"name": "handshake.pcap", "type": "pcap", "desc": "..."}]
    files: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # "curriculum" (hecho a mano) | "template" | "ai"
    generator: Mapped[str] = mapped_column(String(20), default="curriculum", nullable=False)

    # Para retirar un reto sin borrarlo: si tiene envíos, borrarlo rompería el
    # historial y el ranking (la llave foránea de `submissions` lo impide).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Challenge id={self.id!r} points={self.points}>"


class ChallengeInstance(Base):
    __tablename__ = "challenge_instances"

    # Clave primaria compuesta: un jugador tiene como mucho UNA flag personal
    # por reto.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    challenge_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    flag: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ChallengeInstance user_id={self.user_id} challenge_id={self.challenge_id!r}>"
