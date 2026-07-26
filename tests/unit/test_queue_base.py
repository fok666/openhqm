"""Checks for the queue contract, adapter registry, and factory."""

import importlib

import pytest

from openhqm.exceptions import QueueError
from openhqm.queue import Queue, create_queue
from openhqm.queue.base import _ADAPTERS


@pytest.mark.parametrize("qtype", _ADAPTERS)
def test_registered_adapters_implement_queue(qtype):
    module_name, class_name = _ADAPTERS[qtype]
    try:
        cls = getattr(importlib.import_module(module_name), class_name)
    except ImportError:
        pytest.skip(f"{qtype} dependency not installed")
    assert issubclass(cls, Queue)


async def test_create_queue_custom_loads_and_connects(monkeypatch):
    from openhqm.config import settings

    monkeypatch.setattr(settings.queue, "type", "custom")
    monkeypatch.setattr(settings.queue, "custom_module", "tests.unit.fake_queue")
    monkeypatch.setattr(settings.queue, "custom_class", "FakeQueue")
    monkeypatch.setattr(settings.queue, "custom_config", {"marker": 7})

    queue = await create_queue()
    assert queue.connected
    assert queue.marker == 7


async def test_create_queue_custom_requires_module_and_class(monkeypatch):
    from openhqm.config import settings

    monkeypatch.setattr(settings.queue, "type", "custom")
    monkeypatch.setattr(settings.queue, "custom_module", "")

    with pytest.raises(QueueError):
        await create_queue()
