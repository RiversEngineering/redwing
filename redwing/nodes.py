"""Node-based asynchronous programming for advanced students.

Nodes are independent units of computation that run concurrently.
Each node has a ``run()`` coroutine that loops forever, reading inputs
and producing outputs. Nodes communicate through named channels.

Example::

    import redwing
    from redwing.nodes import Node, run_nodes

    robot = redwing.Robot()
    sensor = robot.port3.ultrasonic()
    left   = robot.port1.motor()
    right  = robot.port2.motor()


    class ObstacleDetector(Node):
        async def run(self):
            while True:
                dist = sensor.distance
                await self.publish("distance", dist)
                await self.sleep(0.05)


    class DriveController(Node):
        async def run(self):
            while True:
                dist = await self.receive("distance")
                if dist < 20:
                    left.speed  = 0
                    right.speed = 0
                else:
                    left.speed  = 60
                    right.speed = 60


    run_nodes(ObstacleDetector(), DriveController())
"""

from __future__ import annotations

import asyncio
from typing import Any


_channels: dict[str, asyncio.Queue] = {}
_subscribers: dict[str, list[asyncio.Queue]] = {}


def _get_or_create_channel(name: str) -> list[asyncio.Queue]:
    return _subscribers.setdefault(name, [])


class Node:
    """Base class for all nodes.

    Subclass this and override ``run()`` with your logic. Inside ``run()``,
    use ``await self.publish(name, value)`` to send data and
    ``await self.receive(name)`` to wait for data from another node.
    """

    async def run(self):
        """Override this method with your node's logic.

        This coroutine should loop forever (use ``while True:``).
        """
        raise NotImplementedError("Override run() in your Node subclass.")

    async def publish(self, channel: str, value: Any):
        """Send a value to a named channel.

        Any node that is waiting on ``receive(channel)`` will get this value.
        """
        queues = _subscribers.get(channel, [])
        for q in queues:
            await q.put(value)

    async def receive(self, channel: str, timeout: float | None = None) -> Any:
        """Wait for the next value on a named channel.

        Parameters
        ----------
        channel:
            The channel name to listen on.
        timeout:
            If given, raises ``asyncio.TimeoutError`` after this many seconds
            if no value arrives.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        subs = _subscribers.setdefault(channel, [])
        subs.append(q)
        try:
            if timeout is not None:
                value = await asyncio.wait_for(q.get(), timeout=timeout)
            else:
                value = await q.get()
            return value
        finally:
            subs.remove(q)

    async def sleep(self, seconds: float):
        """Pause this node for the given number of seconds."""
        await asyncio.sleep(seconds)


def run_nodes(*nodes: Node):
    """Start all nodes and run them concurrently until the program is stopped.

    This is a blocking call — put it at the end of your program.

    Example::

        run_nodes(ObstacleDetector(), DriveController(), CameraTracker())
    """
    async def _main():
        tasks = [asyncio.create_task(node.run()) for node in nodes]
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            for task in tasks:
                task.cancel()

    asyncio.run(_main())
