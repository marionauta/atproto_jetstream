from aiohttp.client import ClientSession, ClientWebSocketResponse
from types import TracebackType
from typing import Any, Literal, NamedTuple
from urllib.parse import urlencode


class JetstreamOptions(NamedTuple):
    wanted_collections: list[str] = []
    wanted_dids: list[str] = []
    max_message_size_bytes: int | None = None
    cursor: int | None = None

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

    type Commit = DeleteCommit | CreateUpdateCommit

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


type JetstreamEvent = (
    JetstreamAccountEvent | JetstreamCommitEvent | JetstreamIdentityEvent
)


class Jetstream:
    _url: str
    _options: "JetstreamOptions"
    _client: ClientSession
    _session: ClientWebSocketResponse | None

    def __init__(self, host: str, options: JetstreamOptions | None = None) -> None:
        self._url = host
        self._options = options or JetstreamOptions()
        self._client = ClientSession()
        self._session = None

    async def __aenter__(self) -> "Jetstream":
        _ = await self._client.__aenter__()
        url = f"wss://{self._url}/subscribe?{self._options.to_query()}"
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

    def __aiter__(self):
        if self._session:
            _ = self._session.__aiter__()
        return self

    async def __anext__(self) -> JetstreamEvent:
        if not self._session:
            raise Exception("there's no _session")
        wsm = await self._session.__anext__()
        json: dict[str, Any] = wsm.json()
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
