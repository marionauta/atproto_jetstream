from asyncio import run

from atproto_jetstream import Jetstream, JetstreamOptions


async def main():
    options = JetstreamOptions(compress=True)
    async with Jetstream("jetstream1.us-east.bsky.network", options=options) as stream:
        async for event in stream:
            match event.kind:
                case "account":
                    print(event.account)
                case "identity":
                    print(event.identity)
                case "commit":
                    print(event.commit)


if __name__ == "__main__":
    run(main())
