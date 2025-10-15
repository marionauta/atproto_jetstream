from asyncio import run
from atproto_jetstream import Jetstream


async def main():
    async with Jetstream("jetstream1.us-east.bsky.network") as stream:
        async for message in stream:
            match message.kind:
                case "account":
                    print(message.account)
                case "identity":
                    print(message.identity)
                case "commit":
                    print(message.commit)


if __name__ == "__main__":
    run(main())
