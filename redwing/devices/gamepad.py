"""Gamepad device — reads controller input from the daemon state stream.

Works transparently with both the virtual controller (dashboard tab)
and a physical USB/wireless gamepad connected to the Pi (e.g. GameSir Nova
Lite). No configuration or ``robot.start()`` call is required — just read
the properties at any time in your loop.

Two kinds of button properties
-------------------------------
``robot.gamepad.a``
    **Level** — True for every loop iteration the button is held down.
    Use for continuous actions (driving, holding an arm up).

``robot.gamepad.just_pressed_a``
    **Edge** — True only on the *first* check after the button goes down,
    then False for every subsequent check until the button is released and
    pressed again.  Use for one-shot actions (toggling a mode, firing once).

Example::

    arm_up = False

    while True:
        # Continuous: drive while stick is pushed
        motor.speed = robot.gamepad.left_y * 100

        # Edge: toggle arm position on each A press (not every loop tick)
        if robot.gamepad.just_pressed_a:
            arm_up = not arm_up
            arm.angle = 90 if arm_up else 0

        # Level: hold B to run the intake
        intake.speed = 80 if robot.gamepad.b else 0

        robot.sleep(0.02)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Connection

# Analog triggers are considered "pressed" above this threshold.
_TRIGGER_THRESHOLD = 0.1


class Gamepad:
    """Read-only access to gamepad axes and buttons.

    Axes return floats in **-1.0 … +1.0**.
    Boolean buttons return **True** while held.
    ``just_pressed_*`` properties return **True only once per press**.
    """

    def __init__(self, conn: "Connection"):
        self._conn = conn
        # Stores the previous boolean state for each just_pressed edge detector.
        # Keys match the gamepad dict keys (plus "_edge" suffix for analog inputs).
        self._prev: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gp(self) -> dict:
        return self._conn.get_all_state().get("gamepad", {})

    def _edge(self, key: str, current: bool) -> bool:
        """Rising-edge detector: True only on the first True after a False."""
        was = self._prev.get(key, False)
        self._prev[key] = current
        return current and not was

    # ------------------------------------------------------------------
    # Analog sticks
    # ------------------------------------------------------------------

    @property
    def left_x(self) -> float:
        """Left stick horizontal. -1.0 = full left, +1.0 = full right."""
        return float(self._gp().get("lx", 0.0))

    @property
    def left_y(self) -> float:
        """Left stick vertical. +1.0 = pushed forward, -1.0 = pulled back."""
        return float(self._gp().get("ly", 0.0))

    @property
    def right_x(self) -> float:
        """Right stick horizontal. -1.0 = full left, +1.0 = full right."""
        return float(self._gp().get("rx", 0.0))

    @property
    def right_y(self) -> float:
        """Right stick vertical. +1.0 = pushed forward, -1.0 = pulled back."""
        return float(self._gp().get("ry", 0.0))

    # ------------------------------------------------------------------
    # Face buttons — level (held) and edge (just pressed)
    # ------------------------------------------------------------------

    @property
    def a(self) -> bool:
        """A button — True while held."""
        return bool(self._gp().get("a", False))

    @property
    def just_pressed_a(self) -> bool:
        """True once per press of A (rising edge only)."""
        return self._edge("a", bool(self._gp().get("a", False)))

    @property
    def b(self) -> bool:
        """B button — True while held."""
        return bool(self._gp().get("b", False))

    @property
    def just_pressed_b(self) -> bool:
        """True once per press of B (rising edge only)."""
        return self._edge("b", bool(self._gp().get("b", False)))

    @property
    def x(self) -> bool:
        """X button — True while held."""
        return bool(self._gp().get("x", False))

    @property
    def just_pressed_x(self) -> bool:
        """True once per press of X (rising edge only)."""
        return self._edge("x", bool(self._gp().get("x", False)))

    @property
    def y(self) -> bool:
        """Y button — True while held."""
        return bool(self._gp().get("y", False))

    @property
    def just_pressed_y(self) -> bool:
        """True once per press of Y (rising edge only)."""
        return self._edge("y", bool(self._gp().get("y", False)))

    # ------------------------------------------------------------------
    # D-pad — level and edge
    # ------------------------------------------------------------------

    @property
    def dpad_up(self) -> bool:
        """D-pad up — True while held."""
        return bool(self._gp().get("up", False))

    @property
    def just_pressed_dpad_up(self) -> bool:
        """True once per press of D-pad up."""
        return self._edge("up", bool(self._gp().get("up", False)))

    @property
    def dpad_down(self) -> bool:
        """D-pad down — True while held."""
        return bool(self._gp().get("down", False))

    @property
    def just_pressed_dpad_down(self) -> bool:
        """True once per press of D-pad down."""
        return self._edge("down", bool(self._gp().get("down", False)))

    @property
    def dpad_left(self) -> bool:
        """D-pad left — True while held."""
        return bool(self._gp().get("left", False))

    @property
    def just_pressed_dpad_left(self) -> bool:
        """True once per press of D-pad left."""
        return self._edge("left", bool(self._gp().get("left", False)))

    @property
    def dpad_right(self) -> bool:
        """D-pad right — True while held."""
        return bool(self._gp().get("right", False))

    @property
    def just_pressed_dpad_right(self) -> bool:
        """True once per press of D-pad right."""
        return self._edge("right", bool(self._gp().get("right", False)))

    # ------------------------------------------------------------------
    # Shoulder buttons — level and edge
    # ------------------------------------------------------------------

    @property
    def lb(self) -> bool:
        """Left bumper — True while held."""
        return bool(self._gp().get("lb", False))

    @property
    def just_pressed_lb(self) -> bool:
        """True once per press of LB."""
        return self._edge("lb", bool(self._gp().get("lb", False)))

    @property
    def rb(self) -> bool:
        """Right bumper — True while held."""
        return bool(self._gp().get("rb", False))

    @property
    def just_pressed_rb(self) -> bool:
        """True once per press of RB."""
        return self._edge("rb", bool(self._gp().get("rb", False)))

    @property
    def lt(self) -> float:
        """Left trigger. 0.0 = released, 1.0 = fully pressed."""
        return float(self._gp().get("lt", 0.0))

    @property
    def just_pressed_lt(self) -> bool:
        """True once when LT crosses the press threshold (> 0.1)."""
        return self._edge("lt_edge", float(self._gp().get("lt", 0.0)) > _TRIGGER_THRESHOLD)

    @property
    def rt(self) -> float:
        """Right trigger. 0.0 = released, 1.0 = fully pressed."""
        return float(self._gp().get("rt", 0.0))

    @property
    def just_pressed_rt(self) -> bool:
        """True once when RT crosses the press threshold (> 0.1)."""
        return self._edge("rt_edge", float(self._gp().get("rt", 0.0)) > _TRIGGER_THRESHOLD)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """True if a controller (virtual or physical) has sent input."""
        return bool(self._gp().get("connected", False))

    @property
    def source(self) -> str:
        """Input source: ``"virtual"``, ``"physical"``, or ``"none"``."""
        return str(self._gp().get("source", "none"))
