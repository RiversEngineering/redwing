"""Gamepad device — reads controller input from the daemon state stream.

Works transparently with both the virtual controller (dashboard iPad tab)
and a physical USB/wireless gamepad connected to the Pi (e.g. GameSir Nova
Lite). No configuration or ``robot.start()`` call is required — just read
the properties at any time in your loop.

Example::

    while True:
        # Tank drive: left stick controls left motor, right stick controls right
        left.speed  = robot.gamepad.left_y * 100
        right.speed = robot.gamepad.left_y * 100

        # Turn with right stick X
        turn = robot.gamepad.right_x * 40
        left.speed  -= turn
        right.speed += turn

        if robot.gamepad.a:
            arm.angle = 90       # press A to raise arm
        elif robot.gamepad.b:
            arm.angle = 0        # press B to lower arm

        robot.sleep(0.02)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Connection


class Gamepad:
    """Provides read-only access to gamepad axes and buttons.

    Axes return floats in the range **-1.0 to +1.0**:
      - Positive left_y  = stick pushed forward / up
      - Positive right_x = stick pushed right

    Buttons return **True** while held, **False** when released.
    D-pad directions are separate boolean properties.

    The ``connected`` property is ``True`` when any controller has sent
    input recently.  The ``source`` property reports ``"virtual"`` (iPad
    dashboard) or ``"physical"`` (USB/wireless gamepad), so you can show
    different UI hints if needed — but most code can ignore both.
    """

    def __init__(self, conn: "Connection"):
        self._conn = conn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gp(self) -> dict:
        return self._conn.get_all_state().get("gamepad", {})

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
    # Face buttons (ABXY — Xbox layout)
    # ------------------------------------------------------------------

    @property
    def a(self) -> bool:
        """A button (bottom face button — green on Xbox)."""
        return bool(self._gp().get("a", False))

    @property
    def b(self) -> bool:
        """B button (right face button — red on Xbox)."""
        return bool(self._gp().get("b", False))

    @property
    def x(self) -> bool:
        """X button (left face button — blue on Xbox)."""
        return bool(self._gp().get("x", False))

    @property
    def y(self) -> bool:
        """Y button (top face button — yellow on Xbox)."""
        return bool(self._gp().get("y", False))

    # ------------------------------------------------------------------
    # D-pad
    # ------------------------------------------------------------------

    @property
    def dpad_up(self) -> bool:
        """D-pad up."""
        return bool(self._gp().get("up", False))

    @property
    def dpad_down(self) -> bool:
        """D-pad down."""
        return bool(self._gp().get("down", False))

    @property
    def dpad_left(self) -> bool:
        """D-pad left."""
        return bool(self._gp().get("left", False))

    @property
    def dpad_right(self) -> bool:
        """D-pad right."""
        return bool(self._gp().get("right", False))

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
