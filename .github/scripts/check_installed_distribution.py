"""Check an installed SDK distribution."""



import asyncio
import sys
from importlib.metadata import version

import rune_sdk
from rune_sdk import AsyncRuneClient, RuneClient


async def main() -> None:
    """Check the installed version and initialize both clients."""
    if version("rune-sdk") != sys.argv[1]:
        raise RuntimeError("Installed distribution version does not match the release")
    if rune_sdk.__version__ != sys.argv[1]:
        raise RuntimeError("Exported SDK version does not match the release")
    with RuneClient(api_key="release-smoke-test"):
        pass
    async with AsyncRuneClient(api_key="release-smoke-test"):
        pass


if __name__ == "__main__":
    asyncio.run(main())
