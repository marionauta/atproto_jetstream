import asyncio
from atproto_jetstream import Jetstream


async def main():
    try:
        async with Jetstream("jetstream1.us-east.bsky.network") as stream:
            async for message in stream:
                match message.kind:
                    case "account":
                        print(message.account.did)
                    case "identity":
                        print(message.identity.handle)
                    case "commit":
                        print(message.commit)

    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
