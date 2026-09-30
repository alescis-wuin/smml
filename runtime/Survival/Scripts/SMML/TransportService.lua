-- SMML Runtime Spine laboratory TransportService.
-- Internal prototype: SurvivalGame.network request/reply transport only.

__SMML_TRANSPORT_SERVICE_FACTORY = function( runtime )
    local transport = {
        serverGame = nil,
        clientGame = nil,
        clientFrames = 0,
        clientTestIndex = 1,
        clientReplies = {},
        clientProbeCompleted = false
    }

    local CLIENT_TESTS = {
        { id = "T-RPC-01", contract = "probe.echo@1", payload = { value = "remote-1" } },
        { id = "T-RPC-02", contract = "probe.unknown@1", payload = {} },
        { id = "T-RPC-03", contract = "probe.throw@1", payload = {} },
        { id = "T-RPC-04", contract = "probe.echo@1", payload = { value = "remote-2" } }
    }

    local function config()
        if type( __SMML_RUNTIME_CONFIG ) == "table" then
            return __SMML_RUNTIME_CONFIG
        end
        return { enabled = false, role = "unconfigured", runId = "UNCONFIGURED" }
    end

    local function emit( eventName, fields )
        if type( runtime ) == "table" and type( runtime.emit ) == "function" then
            runtime.emit( eventName, fields )
        end
    end

    local function enabled()
        local cfg = config()
        return cfg.enabled == true and ( cfg.role == "host" or cfg.role == "client" ) and type( cfg.runId ) == "string"
    end

    local function senderIsHost( player )
        if player == nil or type( sm ) ~= "table" or type( sm.player ) ~= "table" or type( sm.player.getHostPlayer ) ~= "function" then
            return false
        end
        local ok, hostPlayer = pcall( sm.player.getHostPlayer )
        return ok and hostPlayer ~= nil and player.id == hostPlayer.id
    end

    local function sendReply( game, player, requestId, accepted, code, result )
        if game == nil or game.network == nil or player == nil then
            emit( "transport.reply.server", {
                requestId = requestId or "nil",
                accepted = accepted == true,
                code = code or "nil",
                result = "network_unavailable"
            } )
            return false
        end

        local cfg = config()
        local ok, detail = pcall( function()
            game.network:sendToClient( player, "cl_smmlRuntimeReply", {
                __smmlRuntime = true,
                runId = cfg.runId,
                requestId = requestId,
                accepted = accepted == true,
                code = code,
                result = result
            } )
        end )

        emit( "transport.reply.server", {
            requestId = requestId or "nil",
            accepted = accepted == true,
            code = code or "nil",
            result = ok and "sent" or "send_error",
            detail = ok and "ok" or detail
        } )
        return ok
    end

    function transport.onServerCreate( game )
        transport.serverGame = game
        emit( "transport.server.bound", { result = game ~= nil and "ok" or "missing_game" } )
    end

    function transport.onClientCreate( game )
        transport.clientGame = game
        transport.clientFrames = 0
        transport.clientTestIndex = 1
        transport.clientReplies = {}
        transport.clientProbeCompleted = false
        emit( "transport.client.bound", { result = game ~= nil and "ok" or "missing_game" } )
    end

    function transport.sendToServer( contract, payload, requestId )
        local cfg = config()
        local game = transport.clientGame
        if not enabled() or cfg.role ~= "client" or game == nil or game.network == nil then
            emit( "transport.send.client", {
                requestId = requestId or "nil",
                contract = contract or "nil",
                result = "network_unavailable"
            } )
            return false
        end

        local envelope = {
            __smmlRuntime = true,
            runId = cfg.runId,
            requestId = requestId,
            contract = contract,
            payload = payload
        }

        local ok, detail = pcall( function()
            game.network:sendToServer( "sv_smmlRuntimeEnvelope", envelope )
        end )
        emit( "transport.send.client", {
            requestId = requestId or "nil",
            contract = contract or "nil",
            result = ok and "sent" or "send_error",
            detail = ok and "ok" or detail
        } )
        return ok
    end

    function transport.onServerEnvelope( game, envelope, player )
        local cfg = config()
        if not enabled() or cfg.role ~= "host" then
            return
        end

        if type( envelope ) ~= "table" then
            emit( "transport.envelope.server", {
                requestId = "nil",
                contract = "nil",
                senderIsHost = senderIsHost( player ),
                result = "invalid_envelope"
            } )
            return
        end

        local requestId = envelope.requestId
        local contract = envelope.contract
        local remote = not senderIsHost( player )
        emit( "transport.envelope.server", {
            requestId = requestId or "nil",
            contract = contract or "nil",
            senderIsHost = not remote,
            result = "received"
        } )

        if envelope.__smmlRuntime ~= true or envelope.runId ~= cfg.runId then
            sendReply( game, player, requestId, false, "wrong_run", nil )
            return
        end
        if type( requestId ) ~= "string" or requestId == "" or type( contract ) ~= "string" or contract == "" then
            sendReply( game, player, requestId, false, "invalid_envelope", nil )
            return
        end
        if type( runtime.contracts ) ~= "table" or type( runtime.contracts.dispatch ) ~= "function" then
            sendReply( game, player, requestId, false, "registry_unavailable", nil )
            return
        end

        local ok, result = runtime.contracts.dispatch( contract, envelope.payload, {
            source = "transport",
            requestId = requestId,
            player = player,
            senderIsHost = not remote
        } )
        if ok then
            sendReply( game, player, requestId, true, "ok", result )
        else
            sendReply( game, player, requestId, false, result, nil )
        end
    end

    local function maybeCompleteClientProbe()
        if transport.clientProbeCompleted then
            return
        end
        local r1 = transport.clientReplies["T-RPC-01"]
        local r2 = transport.clientReplies["T-RPC-02"]
        local r3 = transport.clientReplies["T-RPC-03"]
        local r4 = transport.clientReplies["T-RPC-04"]
        if r1 == nil or r2 == nil or r3 == nil or r4 == nil then
            return
        end

        transport.clientProbeCompleted = true
        local ok =
            r1.accepted == true and r1.code == "ok" and r1.result == "remote-1" and
            r2.accepted == false and r2.code == "unknown_contract" and
            r3.accepted == false and r3.code == "handler_error" and
            r4.accepted == true and r4.code == "ok" and r4.result == "remote-2"

        emit( "transport.probe.complete", {
            ok = ok,
            echo1 = r1.accepted == true and r1.result == "remote-1",
            unknownRejected = r2.accepted == false and r2.code == "unknown_contract",
            throwIsolated = r3.accepted == false and r3.code == "handler_error",
            recoveryOk = r4.accepted == true and r4.result == "remote-2"
        } )
    end

    function transport.onClientReply( game, params )
        local cfg = config()
        if not enabled() or cfg.role ~= "client" or type( params ) ~= "table" then
            return
        end
        if params.__smmlRuntime ~= true or params.runId ~= cfg.runId or type( params.requestId ) ~= "string" then
            return
        end

        transport.clientReplies[params.requestId] = {
            accepted = params.accepted == true,
            code = params.code,
            result = params.result
        }
        emit( "transport.reply.client", {
            requestId = params.requestId,
            accepted = params.accepted == true,
            code = params.code or "nil",
            result = params.result == nil and "nil" or params.result
        } )
        maybeCompleteClientProbe()
    end

    function transport.onClientUpdate( game, dt )
        local cfg = config()
        if not enabled() or cfg.role ~= "client" or transport.clientProbeCompleted then
            return
        end
        if transport.clientGame == nil then
            transport.clientGame = game
        end

        transport.clientFrames = ( transport.clientFrames or 0 ) + 1
        if transport.clientFrames < 90 then
            return
        end

        if transport.clientTestIndex <= #CLIENT_TESTS and ( transport.clientFrames - 90 ) % 20 == 0 then
            local test = CLIENT_TESTS[transport.clientTestIndex]
            if transport.sendToServer( test.contract, test.payload, test.id ) then
                transport.clientTestIndex = transport.clientTestIndex + 1
            end
        end
    end

    emit( "transport.service.loaded", { result = "ok" } )
    return transport
end
