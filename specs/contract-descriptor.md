# SMML ContractDescriptor v1

Status: **candidate freeze** for GP1 Foundation.

Schema identifier:

```text
smml.contract-descriptor/1
```

JSON Schema:

```text
urn:smml:schema:contract-descriptor:1
```

## 1. Purpose

`ContractDescriptor v1` describes a stable SMML runtime contract independently from the vanilla callback, file, or anchor used to implement it.

It defines:

```text
contractId
version
side
category
payloadSchema
resultSchema
combinationPolicy
errorPolicy
```

The descriptor does not define a vanilla injection point, Hook Pack anchor, network backend, remote-call authorization, package load order, handler implementation, or RPC size/frequency limit.

## 2. Normative decisions

### CD-001 - Logical identity and version

`contractId` is the stable logical identity of a contract. v1 preserves the naming already used by GP0, for example:

```text
runtime.bootstrap
game.serverCreated
carry.resolveInsertTarget
carry.beforeServerDrop
```

An ID contains at least two ASCII `.`-separated segments. Each segment starts with a lower-case ASCII letter and may then contain ASCII letters or digits. Internal capitals are therefore allowed to preserve existing lowerCamelCase names.

`version` is an integer greater than or equal to 1. v1 does not impose an arbitrary upper bound. The canonical contract key is:

```text
<contractId>@<version>
```

`version` is not SemVer. No implicit compatibility exists between `@1` and `@2`. Contract IDs are case-sensitive and are never case-folded during lookup.

A TransportService envelope may carry `contractId` and `contractVersion` separately; lookup must match both exactly.

### CD-002 - `side` describes execution, not transport

v1 values:

```text
client
server
shared
```

- `client`: handlers execute in a client runtime.
- `server`: handlers execute in the authoritative server runtime.
- `shared`: the same contract may be registered and executed independently on both sides.

`shared` never means automatic network delivery.

A ContractDescriptor grants no remote-call permission. Client-to-server or server-to-client exposure requires an explicit transport/binding layer outside this descriptor.

### CD-003 - Categories

v1 categories are:

```text
notification
cancellable
transform
query
service
```

#### notification

An event with no determining result. All effective handlers are called in deterministic runtime order. Return values are ignored.

#### cancellable

An authoritative allow/deny decision. A v1 `cancellable` contract MUST use `side = server`.

Each handler returns the builtin logical schema:

```text
smml.decision/1
```

with exactly two logical values:

```text
allow
deny
```

#### transform

An ordered pipeline. Every handler receives a value valid for the contract schema and returns a new value valid for the same schema.

v1 transforms are endomorphic:

```text
payloadSchema == resultSchema
```

The result is validated after every handler before it becomes the input of the next handler.

#### query

A bounded synchronous request with exactly one effective handler. Zero or multiple effective handlers are an invocation error in v1.

#### service

A stable operation provided by Core or one unique provider. As for `query`, v1 requires exactly one effective handler. A service may return no value or a schema-validated value.

### CD-004 - Schema references

A v1 schema reference is either:

```json
{ "kind": "none" }
```

or a package-local artifact reference:

```json
{
  "kind": "artifact",
  "artifactId": "schema.carry-before-server-drop.payload"
}
```

For cancellable results, v1 also defines the builtin reference:

```json
{
  "kind": "builtin",
  "id": "smml.decision/1"
}
```

An `artifactId` MUST reference an artifact in the same `PackageManifest` as the ContractDescriptor.

ContractDescriptor v1 deliberately does not impose one schema dialect. The referenced artifact type selects the validator. This avoids forcing JSON Schema onto local runtime contracts that may later use normalized engine/runtime references.

If the implementation does not support the referenced schema artifact type, activation MUST fail closed.

### CD-005 - Validation before dispatch

The following invariant is global and not configurable:

```text
invalid payload
-> reject-invocation
-> invoke no handler
```

For a remote envelope, processing is conceptually:

```text
envelope
-> known contractId/version
-> validate payload
-> dispatch
```

Unknown contract IDs and unregistered versions are rejected before dispatch.

### CD-006 - Deterministic handler order

For multi-handler categories, inter-package order is the final Lockfile order.

A package may register at most one effective handler for a contract key on a runtime side. A package needing multiple internal callbacks composes them behind that one handler.

Filesystem discovery order and incidental Lua registration order have no semantic meaning.

### CD-007 - Combination policies

Allowed policies are category-specific:

```text
notification -> all
cancellable  -> deny-wins | first-deny
transform    -> pipeline
query        -> single-handler
service      -> single-handler
```

`all` executes all handlers unless the error policy aborts the invocation.

`deny-wins` evaluates all applicable handlers; any effective `deny` makes the final result `deny`.

`first-deny` evaluates handlers in deterministic order and short-circuits on the first effective `deny`.

`pipeline` feeds each valid handler result into the next handler.

`single-handler` requires exactly one effective handler. More than one effective handler is a registry/activation error and MUST fail closed rather than selecting one by registration order.

### CD-008 - Error policy

`errorPolicy` is explicit and contains:

```text
invalidPayload
handlerException
invalidResult
noHandlers
```

`invalidPayload` is always:

```text
reject-invocation
```

Other values depend on category.

#### notification

```text
handlerException = continue | fail-invocation
invalidResult    = not-applicable
noHandlers       = succeed
```

#### cancellable

```text
handlerException = continue | deny | fail-invocation
invalidResult    = continue | deny | fail-invocation
noHandlers       = allow | deny
```

`continue` ignores only the failing handler and continues dispatch. If this leaves no effective decision, `noHandlers` supplies the final fallback decision.

For cancellable contracts, an error policy action of `deny` produces an effective `deny` and is then processed by the selected combination policy. Therefore `first-deny` short-circuits on such a synthetic deny, while `deny-wins` records the deny and continues evaluating remaining handlers. `fail-invocation` aborts only the current invocation after error isolation.

#### transform

```text
handlerException = keep-current | fail-invocation
invalidResult    = keep-current | fail-invocation
noHandlers       = identity
```

`keep-current` retains the last valid value and continues the pipeline. If no handler produces a new valid value, the transform is the identity operation.

#### query

```text
handlerException = fail-invocation
invalidResult    = fail-invocation
noHandlers       = fail-invocation
```

#### service

```text
handlerException = fail-invocation
invalidResult    = fail-invocation | not-applicable
noHandlers       = fail-invocation
```

For a service, `invalidResult = not-applicable` is valid only when `resultSchema.kind = none`.

`noHandlers` is the fallback when dispatch produces no effective handler result. This includes the literal absence of handlers and, for a cancellable contract, the case where all handlers were skipped by an explicit `continue` error policy.

### CD-009 - Handler error isolation

Handlers run behind the runtime isolation boundary already established by GP0:

```text
xpcall(handler, errorAdapter)
```

A handler exception must not corrupt the global dispatcher. The descriptor only decides the consequence for the current invocation after the error has been isolated.

Runtime diagnostics must be able to associate at least package/mod identity, contract ID, contract version, phase/callback, build, and world/session token.

### CD-010 - Cancellable authority

A v1 cancellable contract is server-side because the determining decision must remain authoritative.

A client intent may reach a server contract through TransportService, but:

```text
client intent != server decision
```

### CD-011 - Contract independence from Hook Packs

A mod depends on a stable key such as:

```text
carry.beforeServerDrop@1
```

It does not depend on `CarryTool.lua`, `sv_n_dropCarry`, a vanilla line, an anchor, or one particular Hook Pack.

The boundary remains:

```text
Vanilla
  -> Hook Pack
  -> Adapter
  -> SMML Contract
  -> Mod
```

The future HookPackManifest will declare which adapters/contracts it can provide for a target.

### CD-012 - RPC versus replicated state

ContractDescriptor describes point-in-time invocations. It does not turn `setClientData` into an event bus and does not describe replicated server state.

```text
RPC / point invocation != replicated state
```

### CD-013 - Limits and performance remain open

v1 does not invent values for payload size limits, invocation frequency, RPC quotas, timeouts, handler time budgets, or backpressure. Those remain explicit open questions.

## 3. Examples

### Server notification

```json
{
  "schema": "smml.contract-descriptor/1",
  "contractId": "game.serverCreated",
  "version": 1,
  "side": "server",
  "category": "notification",
  "payloadSchema": {
    "kind": "artifact",
    "artifactId": "schema.game-server-created.payload"
  },
  "resultSchema": { "kind": "none" },
  "combinationPolicy": "all",
  "errorPolicy": {
    "invalidPayload": "reject-invocation",
    "handlerException": "continue",
    "invalidResult": "not-applicable",
    "noHandlers": "succeed"
  }
}
```

### Server cancellable

```json
{
  "schema": "smml.contract-descriptor/1",
  "contractId": "carry.beforeServerDrop",
  "version": 1,
  "side": "server",
  "category": "cancellable",
  "payloadSchema": {
    "kind": "artifact",
    "artifactId": "schema.carry-before-server-drop.payload"
  },
  "resultSchema": {
    "kind": "builtin",
    "id": "smml.decision/1"
  },
  "combinationPolicy": "deny-wins",
  "errorPolicy": {
    "invalidPayload": "reject-invocation",
    "handlerException": "deny",
    "invalidResult": "deny",
    "noHandlers": "allow"
  }
}
```

### Client transform

```json
{
  "schema": "smml.contract-descriptor/1",
  "contractId": "carry.resolveInsertTarget",
  "version": 1,
  "side": "client",
  "category": "transform",
  "payloadSchema": {
    "kind": "artifact",
    "artifactId": "schema.carry-insert-context"
  },
  "resultSchema": {
    "kind": "artifact",
    "artifactId": "schema.carry-insert-context"
  },
  "combinationPolicy": "pipeline",
  "errorPolicy": {
    "invalidPayload": "reject-invocation",
    "handlerException": "keep-current",
    "invalidResult": "keep-current",
    "noHandlers": "identity"
  }
}
```

## 4. Testable invariants

A conforming implementation must at minimum verify:

1. canonical `contractId` form and `version >= 1`;
2. canonical key is exactly `<contractId>@<version>`;
3. no implicit version compatibility;
4. `side` grants no network permission;
5. cancellable contracts are server-side in v1;
6. combination policies are strictly category-specific;
7. notification result schema is `none`;
8. cancellable result schema is builtin `smml.decision/1`;
9. transform input/output are artifact schema refs;
10. transform input/output refs are identical;
11. query has an artifact result schema;
12. service never uses `smml.decision/1` as its result;
13. `invalidPayload = reject-invocation` for every category;
14. error policy values match the category;
15. service + no result implies `invalidResult = not-applicable`;
16. service + artifact result implies `invalidResult = fail-invocation`;
17. every artifact schema ref exists in the associated PackageManifest;
18. a resolved registry has at most one descriptor definition per contract key;
19. a package registers at most one effective handler per key/side;
20. multi-handler order comes from the Lockfile, never filesystem/registration order.

## 5. Out of scope for v1

- final runtime/value schema format;
- validation of referenced schema artifact contents;
- network bindings and transport ACLs;
- payload/frequency/timeout limits;
- replicated state;
- final Lua registration API;
- final diagnostics/log format;
- automatic contract version negotiation;
- deprecation/version aliases;
- Hook Pack anchors/preconditions;
- provider selection by the Resolver.
