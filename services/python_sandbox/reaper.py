"""Independent timer; remove only expired labelled sandbox containers and tmpfs volumes."""
import asyncio
import os
from .engine import Engine


async def main():
    engine = Engine(os.environ['PYTHON_SANDBOX_SOCKET'], os.environ['PYTHON_SANDBOX_IMAGE'])
    try:
        print('orphans_removed=' + str(await engine.reap()))
    finally:
        await engine.client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
