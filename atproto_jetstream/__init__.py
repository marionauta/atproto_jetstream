from compression.zstd import ZstdDict, decompress
from json import loads as json_loads
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, NamedTuple
from urllib.parse import urlencode

from aiohttp import WSMsgType
from aiohttp.client import ClientSession, ClientWebSocketResponse


class JetstreamOptions(NamedTuple):
    endpoint: str = "wss://jetstream1.us-east.bsky.network/subscribe"
    wanted_collections: list[str] = []
    wanted_dids: list[str] = []
    max_message_size_bytes: int | None = None
    cursor: int | None = None
    compress: bool = False

    def to_query(self) -> str:
        params: list[tuple[str, str]] = []
        for collection in self.wanted_collections:
            params.append(("wantedCollections", collection))
        for did in self.wanted_dids:
            params.append(("wantedDids", did))
        if self.max_message_size_bytes is not None:
            params.append(("maxMessageSizeBytes", str(self.max_message_size_bytes)))
        if self.cursor is not None:
            params.append(("cursor", str(self.cursor)))
        if self.compress:
            params.append(("compress", "true"))
        return urlencode(params)


class JetstreamCommitEvent(NamedTuple):
    class DeleteCommit(NamedTuple):
        rev: str
        operation: Literal["delete"]
        collection: str
        rkey: str

    class CreateUpdateCommit(NamedTuple):
        rev: str
        operation: Literal["create", "update"]
        collection: str
        rkey: str
        record: dict[str, Any]
        cid: str

    Commit = DeleteCommit | CreateUpdateCommit

    did: str
    time_us: int
    kind: Literal["commit"]
    commit: Commit


class JetstreamIdentityEvent(NamedTuple):
    class Identity(NamedTuple):
        did: str
        seq: int
        time: str
        handle: str | None = None

    did: str
    time_us: int
    kind: Literal["identity"]
    identity: Identity


class JetstreamAccountEvent(NamedTuple):
    class Account(NamedTuple):
        active: bool
        did: str
        seq: int
        time: str
        status: Literal["active", "deactivated", "takendown"] | None = None

    did: str
    time_us: int
    kind: Literal["account"]
    account: Account


JetstreamEvent = JetstreamAccountEvent | JetstreamCommitEvent | JetstreamIdentityEvent


class Jetstream:
    _options: JetstreamOptions
    _client: ClientSession
    _session: ClientWebSocketResponse | None
    _zstd_dict: ZstdDict

    def __init__(self, options: JetstreamOptions | None = None) -> None:
        self._options = options or JetstreamOptions()
        self._client = ClientSession(auto_decompress=True)
        self._session = None
        if self._options.compress:
            with open(Path(__file__).with_name("zstd_dictionary"), "rb") as file:
                self._zstd_dict = ZstdDict(file.read())

    async def __aenter__(self) -> Jetstream:
        _ = await self._client.__aenter__()
        url = f"{self._options.endpoint}?{self._options.to_query()}"
        self._session = await self._client.ws_connect(url)
        _ = await self._session.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._session:
            await self._session.__aexit__(exc_type, exc_val, exc_tb)
        await self._client.__aexit__(exc_type, exc_val, exc_tb)

    def __aiter__(self) -> Jetstream:
        if self._session:
            _ = self._session.__aiter__()
        return self

    async def __anext__(self) -> JetstreamEvent:
        if not self._session:
            raise Exception("there's no _session")

        json: dict[str, Any] = {}
        wsm = await self._session.__anext__()
        while len(json) == 0:
            if wsm.type == WSMsgType.TEXT and not self._options.compress:
                json = wsm.json()
            elif wsm.type == WSMsgType.BINARY and self._options.compress:
                json = json_loads(decompress(data=wsm.data, zstd_dict=self._zstd_dict))
            else:
                wsm = await self._session.__anext__()

        match json["kind"]:
            case "account":
                account = JetstreamAccountEvent.Account(**json.pop("account"))
                return JetstreamAccountEvent(account=account, **json)
            case "commit":
                commit_raw: dict[str, Any] = json.pop("commit")
                commit: JetstreamCommitEvent.Commit
                match commit_raw["operation"]:
                    case "delete":
                        commit = JetstreamCommitEvent.DeleteCommit(**commit_raw)
                    case "create" | "update":
                        commit = JetstreamCommitEvent.CreateUpdateCommit(**commit_raw)
                    case operation:
                        raise Exception(f"unknown commit operation {operation}")
                return JetstreamCommitEvent(commit=commit, **json)
            case "identity":
                identity = JetstreamIdentityEvent.Identity(**json.pop("identity"))
                return JetstreamIdentityEvent(identity=identity, **json)
            case kind:
                raise Exception(f"unknown event kind: {kind}")
