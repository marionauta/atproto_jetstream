# atproto_jetstream

Small, typed, and async package to receive [Jetstream][jetstream] events from the [AT Protocol][atproto].

## install

Using your package manager, install the [`atproto_jetstream`][pypi] dependency.

- `pip install atproto_jetstream`
- `uv add atproto_jetstream`

## usage

```python
from asyncio import run
from atproto_jetstream import Jetstream


async def main():
    async with Jetstream("jetstream1.us-east.bsky.network") as stream:
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
```

[atproto]: https://atproto.com/
[jetstream]: https://docs.bsky.app/blog/jetstream
[pypi]: https://pypi.org/project/atproto_jetstream/
