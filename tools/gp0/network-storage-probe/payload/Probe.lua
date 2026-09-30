-- SMML GP0.5 Network / Storage Probe v0.2.0
-- This is research code, not the future public SMML runtime API.

if type( __SMML_GP0_NS ) ~= "table" then
    return
end

local probe = __SMML_GP0_NS
local config = type( __SMML_GP0_NS_CONFIG ) == "table" and __SMML_GP0_NS_CONFIG or { enabled = false, role = "disabled", runId = "UNCONFIGURED" }
local ns = probe.ns or {}
probe.ns = ns

local STORAGE_PREFIX = "SMML_GP0_NS_V020_"
local CLIENT_DATA_CHANNELS = { 3, 4 }

local function enabled()
    return config.enabled == true and ( config.role == "host" or config.role == "client" ) and type( config.runId ) == "string"
end

local function boolText( value )
    return value == true and "true" or "false"
end

local function mark( eventName, fields )
    if type( probe.mark ) == "function" then
        probe.mark( eventName, fields )
    end
end

local function notify( text )
    if type( sm ) == "table" and type( sm.gui ) == "table" and type( sm.gui.chatMessage ) == "function" then
        pcall( sm.gui.chatMessage, "[SMML GP0] " .. tostring( text ) )
    end
end

local function getHostPlayerId()
    if type( sm ) ~= "table" or type( sm.player ) ~= "table" or type( sm.player.getHostPlayer ) ~= "function" then
        return nil
    end
    local ok, hostPlayer = pcall( sm.player.getHostPlayer )
    if not ok or hostPlayer == nil then
        return nil
    end
    return hostPlayer.id
end

local function playerFields( player )
    local playerId = player and player.id or "nil"
    local playerName = player and player.name or "nil"
    local hostId = getHostPlayerId()
    local isHostPlayer = hostId ~= nil and player ~= nil and player.id == hostId
    return playerId, playerName, isHostPlayer
end

local function safeSendToClient( game, player, method, params, label )
    if not game or not game.network then
        mark( "network.send.server.error", { label = label, method = method, reason = "network-unavailable" } )
        return false
    end
    local ok, err = pcall( function()
        game.network:sendToClient( player, method, params )
    end )
    mark( ok and "network.send.server.ok" or "network.send.server.error", {
        label = label,
        method = method,
        detail = ok and "ok" or err
    } )
    return ok
end

local function safeBroadcast( game, method, params, label )
    if not game or not game.network then
        mark( "network.broadcast.server.error", { label = label, method = method, reason = "network-unavailable" } )
        return false
    end
    local ok, err = pcall( function()
        game.network:sendToClients( method, params )
    end )
    mark( ok and "network.broadcast.server.ok" or "network.broadcast.server.error", {
        label = label,
        method = method,
        detail = ok and "ok" or err
    } )
    return ok
end

local function safeSetClientData( game, channel, revision, reason )
    if not game or not game.network then
        mark( "clientdata.set.error", { channel = channel, revision = revision, reason = "network-unavailable" } )
        return false
    end
    local payload = {
        __smmlGp0Ns = true,
        runId = config.runId,
        revision = revision,
        channelProbe = channel,
        reason = reason,
        serverInstanceId = ns.server and ns.server.instanceId or "unknown"
    }
    local ok, err = pcall( function()
        game.network:setClientData( payload, channel )
    end )
    mark( ok and "clientdata.set.ok" or "clientdata.set.error", {
        channel = channel,
        revision = revision,
        reason = reason,
        detail = ok and "ok" or err
    } )
    return ok
end

local function publishClientData( game, revision, reason )
    for _, channel in ipairs( CLIENT_DATA_CHANNELS ) do
        safeSetClientData( game, channel, revision, reason )
    end
end

local function storageKey()
    return STORAGE_PREFIX .. tostring( config.runId )
end

local function validateLogicalNamespaces( root )
    if type( root ) ~= "table" or type( root.namespaces ) ~= "table" then
        return false, "namespaces-missing"
    end
    local a = root.namespaces["com.smml.probe.a"]
    local b = root.namespaces["com.smml.probe.b"]
    if type( a ) ~= "table" or type( b ) ~= "table" then
        return false, "fake-mod-namespace-missing"
    end
    if a.sharedKey ~= "A" or b.sharedKey ~= "B" then
        return false, "shared-key-value-mismatch"
    end
    if a.sharedKey == b.sharedKey then
        return false, "logical-isolation-collision"
    end
    return true, "ok"
end

local function saveStorage( key, value, eventName )
    local ok, err = pcall( function()
        sm.storage.save( key, value )
    end )
    mark( ok and eventName or "storage.save.error", {
        key = key,
        schemaVersion = type( value ) == "table" and value.schemaVersion or "nil",
        namespaceIsolation = type( value ) == "table" and boolText( select( 1, validateLogicalNamespaces( value ) ) ) or "false",
        detail = ok and "ok" or err
    } )
    return ok
end

local function runStoragePhase()
    if config.role ~= "host" then
        mark( "storage.skip", { reason = "non-host-role" } )
        return
    end
    if type( sm ) ~= "table" or type( sm.storage ) ~= "table" or type( sm.storage.load ) ~= "function" or type( sm.storage.save ) ~= "function" then
        mark( "storage.error", { reason = "sm.storage-unavailable" } )
        return
    end

    local key = storageKey()
    local ok, stored = pcall( sm.storage.load, key )
    if not ok then
        mark( "storage.load.error", { key = key, detail = stored } )
        return
    end

    if stored == nil then
        mark( "storage.load.absent", { key = key } )
        local schema1 = {
            marker = "SMML_GP0_NS",
            runId = config.runId,
            schemaVersion = 1,
            namespaces = {
                ["com.smml.probe.a"] = { sharedKey = "A", dataKey = "shared" },
                ["com.smml.probe.b"] = { sharedKey = "B", dataKey = "shared" }
            }
        }
        local valid, detail = validateLogicalNamespaces( schema1 )
        mark( "storage.namespace.check", { phase = "schema1-before-save", success = boolText( valid ), detail = detail } )
        saveStorage( key, schema1, "storage.save.schema1" )
        return
    end

    if type( stored ) ~= "table" then
        mark( "storage.load.foreign", { key = key, storedType = type( stored ) } )
        return
    end

    local valid, detail = validateLogicalNamespaces( stored )
    mark( "storage.namespace.check", {
        phase = "load",
        success = boolText( valid ),
        detail = detail,
        schemaVersion = stored.schemaVersion or "nil"
    } )

    if stored.marker ~= "SMML_GP0_NS" or stored.runId ~= config.runId then
        mark( "storage.load.foreign", {
            key = key,
            marker = stored.marker or "nil",
            storedRunId = stored.runId or "nil",
            schemaVersion = stored.schemaVersion or "nil"
        } )
        return
    end

    if stored.schemaVersion == 1 then
        mark( "storage.load.schema1", { key = key, namespaceIsolation = boolText( valid ) } )
        local schema2 = {
            marker = stored.marker,
            runId = stored.runId,
            schemaVersion = 2,
            migratedFrom = 1,
            namespaces = stored.namespaces,
            migration = { completed = true, source = "gp0.5-probe" }
        }
        local valid2, detail2 = validateLogicalNamespaces( schema2 )
        mark( "storage.migration.1to2", { success = boolText( valid2 ), detail = detail2 } )
        saveStorage( key, schema2, "storage.save.schema2" )
        return
    end

    if stored.schemaVersion == 2 then
        mark( "storage.load.schema2", {
            key = key,
            migratedFrom = stored.migratedFrom or "nil",
            namespaceIsolation = boolText( valid )
        } )
        return
    end

    mark( "storage.load.unknown-schema", { key = key, schemaVersion = stored.schemaVersion or "nil" } )
end

local handlers = {}

handlers["probe.ping@1"] = function( payload, context )
    if type( payload ) ~= "table" or type( payload.marker ) ~= "string" then
        return false, "invalid-ping-payload", nil
    end
    return true, "ok", { pong = payload.marker, senderPlayerId = context.playerId }
end

handlers["probe.echo@1"] = function( payload, context )
    return true, "ok", { payloadType = type( payload ), payload = payload, senderPlayerId = context.playerId }
end

handlers["probe.throw@1"] = function( payload, context )
    error( "intentional GP0.5 handler failure" )
end

local function sendReply( game, player, requestId, accepted, code, result )
    if not player then
        return false
    end
    return safeSendToClient( game, player, "cl_smmlGp0ProbeReply", {
        __smmlGp0Ns = true,
        runId = config.runId,
        requestId = requestId or "nil",
        accepted = accepted == true,
        code = code or "nil",
        result = result
    }, "reply:" .. tostring( requestId ) )
end

function ns.onServerEnvelope( game, envelope, player )
    if not enabled() or config.role ~= "host" then
        return
    end

    local playerId, playerName, senderIsHost = playerFields( player )
    if type( envelope ) ~= "table" then
        mark( "network.envelope.reject", {
            reason = "envelope-not-table",
            envelopeType = type( envelope ),
            playerId = playerId,
            playerName = playerName,
            senderIsHost = boolText( senderIsHost )
        } )
        return
    end

    local requestId = envelope.requestId or "nil"
    mark( "network.envelope.server", {
        requestId = requestId,
        contractId = envelope.contractId or "nil",
        contractVersion = envelope.contractVersion or "nil",
        payloadType = type( envelope.payload ),
        playerId = playerId,
        playerName = playerName,
        senderIsHost = boolText( senderIsHost )
    } )

    if envelope.__smmlGp0Ns ~= true or envelope.runId ~= config.runId then
        mark( "network.envelope.reject", {
            requestId = requestId,
            reason = "wrong-probe-or-run",
            playerId = playerId,
            senderIsHost = boolText( senderIsHost )
        } )
        sendReply( game, player, requestId, false, "wrong-probe-or-run", nil )
        return
    end

    if type( envelope.contractId ) ~= "string" or type( envelope.contractVersion ) ~= "number" then
        mark( "network.envelope.reject", {
            requestId = requestId,
            reason = "invalid-contract-descriptor",
            playerId = playerId,
            senderIsHost = boolText( senderIsHost )
        } )
        sendReply( game, player, requestId, false, "invalid-contract-descriptor", nil )
        return
    end

    local key = envelope.contractId .. "@" .. tostring( envelope.contractVersion )
    local handler = handlers[key]
    if type( handler ) ~= "function" then
        mark( "network.envelope.reject", {
            requestId = requestId,
            reason = "unknown-contract",
            contractKey = key,
            playerId = playerId,
            senderIsHost = boolText( senderIsHost )
        } )
        sendReply( game, player, requestId, false, "unknown-contract", nil )
        return
    end

    local context = {
        playerId = playerId,
        playerName = playerName,
        senderIsHost = senderIsHost,
        requestId = requestId
    }

    local ok, accepted, code, result = xpcall(
        function()
            return handler( envelope.payload, context )
        end,
        function( err )
            return tostring( err )
        end
    )

    if not ok then
        mark( "network.handler.error", {
            requestId = requestId,
            contractKey = key,
            detail = accepted,
            playerId = playerId,
            senderIsHost = boolText( senderIsHost )
        } )
        sendReply( game, player, requestId, false, "handler-error", nil )
        return
    end

    if accepted ~= true then
        mark( "network.handler.reject", {
            requestId = requestId,
            contractKey = key,
            code = code or "rejected",
            playerId = playerId,
            senderIsHost = boolText( senderIsHost )
        } )
        sendReply( game, player, requestId, false, code or "rejected", result )
        return
    end

    mark( "network.handler.ok", {
        requestId = requestId,
        contractKey = key,
        code = code or "ok",
        playerId = playerId,
        senderIsHost = boolText( senderIsHost )
    } )
    sendReply( game, player, requestId, true, code or "ok", result )

    if not senderIsHost and ns.server then
        if not ns.server.remoteTrafficSeen then
            ns.server.remoteTrafficSeen = true
            safeBroadcast( game, "cl_smmlGp0ProbeBroadcast", {
                __smmlGp0Ns = true,
                runId = config.runId,
                marker = "remote-traffic-first-seen",
                serverInstanceId = ns.server.instanceId
            }, "first-remote-traffic" )
        end
        if not ns.server.clientDataRemoteUpdateDone then
            ns.server.clientDataRemoteUpdateDone = true
            publishClientData( game, 2, "remote-traffic" )
        end
    end
end

function ns.onClientReply( game, params )
    if not enabled() or type( params ) ~= "table" or params.__smmlGp0Ns ~= true or params.runId ~= config.runId then
        return
    end
    mark( "network.reply.client", {
        requestId = params.requestId or "nil",
        accepted = boolText( params.accepted == true ),
        code = params.code or "nil",
        resultType = type( params.result ),
        localRole = config.role,
        localSmIsHost = boolText( type( sm ) == "table" and sm.isHost == true )
    } )
    if config.role == "client" and params.requestId == "N-RPC-10" and params.accepted == true then
        notify( "matrice RPC terminee; quitte puis rejoins une fois la partie pour tester le reconnect." )
    end
end

function ns.onClientBroadcast( game, params )
    if not enabled() or type( params ) ~= "table" or params.__smmlGp0Ns ~= true or params.runId ~= config.runId then
        return
    end
    mark( "network.broadcast.client", {
        marker = params.marker or "nil",
        serverInstanceId = params.serverInstanceId or "nil",
        localRole = config.role,
        localSmIsHost = boolText( type( sm ) == "table" and sm.isHost == true )
    } )
end

function ns.onClientDataUpdate( game, clientData, channel )
    if not enabled() or type( clientData ) ~= "table" or clientData.__smmlGp0Ns ~= true or clientData.runId ~= config.runId then
        return
    end
    mark( "clientdata.receive.client", {
        channel = channel,
        revision = clientData.revision or "nil",
        channelProbe = clientData.channelProbe or "nil",
        reason = clientData.reason or "nil",
        serverInstanceId = clientData.serverInstanceId or "nil",
        localRole = config.role,
        localSmIsHost = boolText( type( sm ) == "table" and sm.isHost == true )
    } )
end

function ns.onServerCreate( game )
    ns.server = {
        game = game,
        ticks = 0,
        storageDone = false,
        clientDataInitialDone = false,
        clientDataRemoteUpdateDone = false,
        remoteTrafficSeen = false,
        instanceId = tostring( game )
    }
    mark( "lifecycle.server.create", { instanceId = ns.server.instanceId } )
end

function ns.onServerDestroy( game )
    mark( "lifecycle.server.destroy", { instanceId = ns.server and ns.server.instanceId or tostring( game ) } )
end

function ns.onServerUnload( game )
    mark( "lifecycle.server.unload", { instanceId = ns.server and ns.server.instanceId or tostring( game ) } )
end

function ns.onServerPlayerJoined( game, player, newPlayer )
    local playerId, playerName, isHostPlayer = playerFields( player )
    mark( "lifecycle.player.join", {
        playerId = playerId,
        playerName = playerName,
        isHostPlayer = boolText( isHostPlayer ),
        newPlayer = boolText( newPlayer == true ),
        serverInstanceId = ns.server and ns.server.instanceId or "unknown"
    } )
end

function ns.onServerPlayerLeft( game, player )
    local playerId, playerName, isHostPlayer = playerFields( player )
    mark( "lifecycle.player.left", {
        playerId = playerId,
        playerName = playerName,
        isHostPlayer = boolText( isHostPlayer ),
        serverInstanceId = ns.server and ns.server.instanceId or "unknown"
    } )
end

function ns.onServerFixedUpdate( game, timeStep )
    if not enabled() or config.role ~= "host" or not ns.server then
        return
    end
    ns.server.ticks = ( ns.server.ticks or 0 ) + 1

    if not ns.server.storageDone and ns.server.ticks >= 1 then
        ns.server.storageDone = true
        local ok, err = pcall( runStoragePhase )
        if not ok then
            mark( "storage.phase.error", { detail = err } )
        end
    end

    if not ns.server.clientDataInitialDone and ns.server.ticks >= 40 then
        ns.server.clientDataInitialDone = true
        publishClientData( game, 1, "initial-server-state" )
    end
end

local CLIENT_TESTS = {
    { id = "N-RPC-01", contractId = "probe.ping", contractVersion = 1, payload = { marker = "remote-basic" } },
    { id = "N-RPC-02", contractId = "probe.echo", contractVersion = 1, payload = true },
    { id = "N-RPC-03", contractId = "probe.echo", contractVersion = 1, payload = 123.5 },
    { id = "N-RPC-04", contractId = "probe.echo", contractVersion = 1, payload = "hello-from-remote-client" },
    { id = "N-RPC-05", contractId = "probe.echo", contractVersion = 1, payload = { outer = { inner = "nested", value = 42 }, flag = true } },
    { id = "N-RPC-06", contractId = "probe.unknown", contractVersion = 1, payload = { marker = "unknown-contract" } },
    { id = "N-RPC-07", contractId = "probe.ping", contractVersion = 999, payload = { marker = "bad-version" } },
    { id = "N-RPC-08", contractId = "probe.ping", contractVersion = 1, payload = "invalid-payload" },
    { id = "N-RPC-09", contractId = "probe.throw", contractVersion = 1, payload = { marker = "intentional-throw" } },
    { id = "N-RPC-10", contractId = "probe.ping", contractVersion = 1, payload = { marker = "post-throw" } }
}

local function safeSendToServer( game, test )
    if not game or not game.network then
        mark( "network.send.client.error", { requestId = test.id, reason = "network-unavailable" } )
        return false
    end
    local envelope = {
        __smmlGp0Ns = true,
        runId = config.runId,
        requestId = test.id,
        contractId = test.contractId,
        contractVersion = test.contractVersion,
        payload = test.payload
    }
    local ok, err = pcall( function()
        game.network:sendToServer( "sv_smmlGp0ProbeEnvelope", envelope )
    end )
    mark( ok and "network.send.client.ok" or "network.send.client.error", {
        requestId = test.id,
        contractId = test.contractId,
        contractVersion = test.contractVersion,
        payloadType = type( test.payload ),
        detail = ok and "ok" or err
    } )
    return ok
end

local function safeSendNilEnvelope( game )
    if not game or not game.network then
        mark( "network.send.client.error", { requestId = "N-RPC-11", reason = "network-unavailable" } )
        return false
    end
    local ok, err = pcall( function()
        game.network:sendToServer( "sv_smmlGp0ProbeEnvelope", nil )
    end )
    mark( ok and "network.send.client.ok" or "network.send.client.error", {
        requestId = "N-RPC-11",
        contractId = "nil-envelope",
        payloadType = "nil",
        detail = ok and "ok" or err
    } )
    return ok
end

function ns.onClientCreate( game )
    ns.client = {
        game = game,
        frames = 0,
        testIndex = 1,
        nilEnvelopeSent = false,
        matrixComplete = false,
        instanceId = tostring( game )
    }
    mark( "lifecycle.client.create", {
        instanceId = ns.client.instanceId,
        localRole = config.role,
        localSmIsHost = boolText( type( sm ) == "table" and sm.isHost == true )
    } )
end

function ns.onClientUpdate( game, dt )
    if not enabled() or not ns.client then
        return
    end
    ns.client.frames = ( ns.client.frames or 0 ) + 1

    if config.role ~= "client" then
        return
    end

    if ns.client.frames < 90 then
        return
    end

    if ns.client.testIndex <= #CLIENT_TESTS then
        if ( ns.client.frames - 90 ) % 20 == 0 then
            local test = CLIENT_TESTS[ns.client.testIndex]
            safeSendToServer( game, test )
            ns.client.testIndex = ns.client.testIndex + 1
        end
        return
    end

    if not ns.client.nilEnvelopeSent and ( ns.client.frames - 90 ) % 20 == 0 then
        ns.client.nilEnvelopeSent = true
        safeSendNilEnvelope( game )
        return
    end

    if ns.client.nilEnvelopeSent and not ns.client.matrixComplete then
        ns.client.matrixComplete = true
        mark( "network.matrix.sent", { tests = #CLIENT_TESTS + 1 } )
    end
end

mark( "probe.module.ready", {
    enabled = enabled(),
    configuredRole = config.role or "disabled",
    storageKey = enabled() and storageKey() or "disabled"
} )
