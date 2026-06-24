"""
Máquina de estados del bot de fichaje (lógica pura, sin red).

Estados de partida (los que ya clasifica el dashboard: classifyPresenceRecord):
  OUT      -> fuera / no trabajando
  WORKING  -> trabajando
  PAUSED   -> en pausa
  REMOTE   -> teletrabajo (se trata como WORKING a efectos de toggle)

Acciones atómicas (las traduce a HTTP el sesame_client):
  CLOCK_IN     -> abre jornada (check-in, workCheckTypeId=null)
  CLOCK_OUT    -> cierra jornada (check-out)
  PAUSE_START  -> inicia tramo de pausa (check con tipo de pausa)
  PAUSE_END    -> termina la pausa y vuelve a trabajar

Decisiones acordadas con Jesús (ver BOT_FICHAJE_PLAN.md):
  F1: 'fichar' estando en pausa -> PAUSE_END + CLOCK_OUT (no se puede cerrar
      jornada con una pausa abierta).
  P2: 'pausar' estando fuera -> NO se inventa una micro-jornada; el bot pide
      confirmación y, si acepta, CLOCK_IN + PAUSE_START (una sola jornada,
      abierta y en pausa). Más limpio que el "ficho 1s y cierro".
"""

from dataclasses import dataclass, field

OUT, WORKING, PAUSED, REMOTE = "out", "working", "paused", "remote"

CLOCK_IN, CLOCK_OUT = "CLOCK_IN", "CLOCK_OUT"
PAUSE_START, PAUSE_END = "PAUSE_START", "PAUSE_END"

FICHAR, PAUSAR = "fichar", "pausar"


@dataclass
class Plan:
    actions: list = field(default_factory=list)   # secuencia de acciones atómicas
    needs_confirmation: bool = False               # exige [Sí]/[No] antes de ejecutar
    description: str = ""                           # qué se va a hacer (para el usuario)
    note: str = ""                                  # avisos / ambigüedades


def plan_actions(state: str, command: str) -> Plan:
    """Dado el estado actual del empleado y el comando, devuelve el plan de acciones.
    NO ejecuta nada: solo decide. La confirmación y la ejecución las hace el bot."""
    s = (state or "").lower()
    is_active = s in (WORKING, REMOTE)   # trabajando o teletrabajando

    if command == FICHAR:
        if s == OUT:
            return Plan([CLOCK_IN], False, "Iniciar jornada")
        if is_active:
            return Plan([CLOCK_OUT], True, "Finalizar jornada")
        if s == PAUSED:
            # F1: cerrar la pausa abierta y luego cerrar la jornada
            return Plan([PAUSE_END, CLOCK_OUT], True,
                        "Cerrar la pausa y finalizar jornada")

    elif command == PAUSAR:
        if is_active:
            return Plan([PAUSE_START], False, "Iniciar pausa")
        if s == PAUSED:
            return Plan([PAUSE_END], False, "Terminar la pausa y volver al trabajo")
        if s == OUT:
            # P2: no hay jornada abierta -> preguntar e iniciar jornada ya en pausa
            return Plan([CLOCK_IN, PAUSE_START], True,
                        "No tienes jornada abierta. Iniciar jornada y entrar en pausa",
                        note="Caso 'pausar estando fuera' (P2).")

    return Plan([], False, "", note=f"Estado/comando no contemplado: {state}/{command}")


# Tabla de transición (para documentar/testear de un vistazo)
TRANSITION_TABLE = {
    (OUT, FICHAR):     "CLOCK_IN",
    (WORKING, FICHAR): "CLOCK_OUT",
    (REMOTE, FICHAR):  "CLOCK_OUT",
    (PAUSED, FICHAR):  "PAUSE_END + CLOCK_OUT",
    (OUT, PAUSAR):     "(confirm) CLOCK_IN + PAUSE_START",
    (WORKING, PAUSAR): "PAUSE_START",
    (REMOTE, PAUSAR):  "PAUSE_START",
    (PAUSED, PAUSAR):  "PAUSE_END",
}


if __name__ == "__main__":
    # Smoke test: imprime la tabla de decisiones (no toca red)
    print("Estado x Comando -> Plan\n" + "-" * 48)
    for st in (OUT, WORKING, REMOTE, PAUSED):
        for cmd in (FICHAR, PAUSAR):
            p = plan_actions(st, cmd)
            conf = " [confirmar]" if p.needs_confirmation else ""
            print(f"{st:8} + {cmd:6} -> {' , '.join(p.actions) or '—':24} {p.description}{conf}")
