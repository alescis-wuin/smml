-- SMML Runtime Spine laboratory Carry adapter.
-- v0.5.2: one resolver targets a vanilla Scrap Chest whose receiver is temporarily supplied by SMML.

__SMML_CARRY_ADAPTER_FACTORY = function( runtime )
    local SCRAP_WOOD_UUID = "968de65c-75f3-471b-954e-6165a4b6d3d6"
    local SCRAP_CHEST_UUID = "7527cf2e-1705-4214-9d07-3dc374957e25"
    local TEST_RESOLVER_ID = "probe.scrapChestReceiver@1"

    local service = {
        resolvers = {},
        resolverCount = 0
    }

    local function safeUuid( value )
        if value == nil then
            return "nil"
        end
        return tostring( value )
    end

    local function captureError( detail )
        return tostring( detail )
    end

    local function emit( eventName, fields )
        if type( runtime ) == "table" and type( runtime.emit ) == "function" then
            runtime.emit( eventName, fields )
        end
    end

    function service.registerResolver( resolverId, resolver )
        if type( resolverId ) ~= "string" or resolverId == "" then
            return false, "invalid_resolver_id"
        end
        if type( resolver ) ~= "function" then
            return false, "invalid_resolver"
        end
        if service.resolvers[resolverId] ~= nil then
            return false, "duplicate_resolver"
        end

        service.resolvers[resolverId] = resolver
        service.resolverCount = service.resolverCount + 1
        emit( "carry.resolver.register", {
            resolverId = resolverId,
            result = "ok",
            resolverCount = service.resolverCount
        } )
        return true
    end

    local function scrapChestReceiverResolver( context )
        if type( context ) ~= "table" or context.resultType ~= "body" or context.raycastResult == nil then
            return nil, "not_body"
        end
        if safeUuid( context.carryUuid ) ~= SCRAP_WOOD_UUID then
            return nil, "unsupported_carry"
        end

        local hitShape = context.raycastResult:getShape()
        if hitShape == nil then
            return nil, "shape_missing"
        end
        if safeUuid( hitShape:getShapeUuid() ) ~= SCRAP_CHEST_UUID then
            return nil, "not_test_receiver"
        end

        return hitShape, "ok"
    end

    service.registerResolver( TEST_RESOLVER_ID, scrapChestReceiverResolver )

    function service.resolveInsertTarget( context )
        if type( context ) ~= "table" then
            return false, nil, nil, "invalid_context"
        end

        local resolverIds = {}
        for resolverId, _ in pairs( service.resolvers ) do
            resolverIds[#resolverIds + 1] = resolverId
        end
        table.sort( resolverIds )

        for _, resolverId in ipairs( resolverIds ) do
            local resolver = service.resolvers[resolverId]
            local ok, targetShape, detail = xpcall( function()
                return resolver( context )
            end, captureError )

            if not ok then
                emit( "carry.resolve.error", {
                    resolverId = resolverId,
                    detail = targetShape
                } )
                return false, nil, resolverId, "resolver_error"
            end

            if targetShape ~= nil then
                if context.isStart == true then
                    local hitShape = context.raycastResult and context.raycastResult:getShape() or nil
                    emit( "carry.resolve.match", {
                        resolverId = resolverId,
                        carryUuid = safeUuid( context.carryUuid ),
                        proxyUuid = hitShape and safeUuid( hitShape:getShapeUuid() ) or "nil",
                        targetUuid = safeUuid( targetShape:getShapeUuid() ),
                        resultType = context.resultType or "nil"
                    } )
                end
                return true, targetShape, resolverId, detail or "ok"
            end
        end

        if context.isStart == true then
            emit( "carry.resolve.empty", {
                carryUuid = safeUuid( context.carryUuid ),
                raycastSuccess = context.raycastSuccess == true,
                resultType = context.resultType or "nil",
                resolverCount = service.resolverCount
            } )
        end

        return false, nil, nil, "no_resolver"
    end

    function service.onResolverClientSend( params )
        emit( "carry.resolver.rpc.client", {
            resolverId = params and params.__smmlResolverId or "nil",
            carryUuid = params and params.itemA or "nil",
            targetUuid = params and params.targetShape and params.targetShape:getShapeUuid() or "nil"
        } )
        return true
    end

    function service.onVanillaServerRelay( params, player )
        emit( "carry.vanilla.rpc.server", {
            carryUuid = params and params.itemA or "nil",
            targetUuid = params and params.targetShape and params.targetShape:getShapeUuid() or "nil",
            playerId = player and player.id or "nil",
            resolverId = params and params.__smmlResolverId or "nil"
        } )

        if params and params.__smmlResolverId == TEST_RESOLVER_ID then
            emit( "carry.resolver.rpc.server", {
                resolverId = params.__smmlResolverId,
                carryUuid = params.itemA or "nil",
                targetUuid = params.targetShape and params.targetShape:getShapeUuid() or "nil",
                playerId = player and player.id or "nil"
            } )
        end
        return true
    end

    local function rejectReceiver( receiver, params, reason, detail )
        emit( "carry.receiver.reject", {
            resolverId = params and params.__smmlResolverId or "nil",
            carryUuid = params and params.itemA or "nil",
            receiverUuid = receiver and receiver.shape and safeUuid( receiver.shape:getShapeUuid() ) or "nil",
            playerId = params and params.player and params.player.id or "nil",
            reason = reason,
            detail = detail or "nil"
        } )
        return false, reason
    end

    function service.onCustomReceiverServer( receiver, params )
        if receiver == nil or receiver.shape == nil then
            return rejectReceiver( receiver, params, "receiver_missing" )
        end
        if safeUuid( receiver.shape:getShapeUuid() ) ~= SCRAP_CHEST_UUID then
            return rejectReceiver( receiver, params, "receiver_uuid_mismatch" )
        end
        if type( params ) ~= "table" or params.__smmlResolverId ~= TEST_RESOLVER_ID then
            return rejectReceiver( receiver, params, "resolver_mismatch" )
        end
        if safeUuid( params.itemA ) ~= SCRAP_WOOD_UUID then
            return rejectReceiver( receiver, params, "unsupported_carry" )
        end
        if tonumber( params.quantityA ) ~= 1 then
            return rejectReceiver( receiver, params, "invalid_quantity", params.quantityA )
        end

        local player = params.player
        if player == nil then
            return rejectReceiver( receiver, params, "player_missing" )
        end

        local carryOk, carry = pcall( function() return player:getCarry() end )
        if not carryOk or carry == nil then
            return rejectReceiver( receiver, params, "carry_missing", carryOk and "nil" or carry )
        end

        local itemUuid = sm.uuid.new( SCRAP_WOOD_UUID )
        if sm.container.totalQuantity( carry, itemUuid ) < 1 then
            return rejectReceiver( receiver, params, "insufficient_carry" )
        end

        local beginOk = sm.container.beginTransaction()
        if beginOk ~= true then
            return rejectReceiver( receiver, params, "transaction_begin_failed" )
        end

        local spendOk, spent = pcall( sm.container.spend, carry, itemUuid, 1, true )
        if not spendOk then
            pcall( sm.container.abortTransaction )
            return rejectReceiver( receiver, params, "spend_error", spent )
        end
        if spent ~= 1 then
            pcall( sm.container.abortTransaction )
            return rejectReceiver( receiver, params, "spend_failed", spent )
        end

        local endOk, committed = pcall( sm.container.endTransaction )
        if not endOk or committed ~= true then
            pcall( sm.container.abortTransaction )
            return rejectReceiver( receiver, params, "transaction_commit_failed", endOk and committed or committed )
        end

        receiver.__smmlReceivedCount = ( receiver.__smmlReceivedCount or 0 ) + 1
        emit( "carry.receiver.accept", {
            resolverId = TEST_RESOLVER_ID,
            carryUuid = SCRAP_WOOD_UUID,
            receiverUuid = SCRAP_CHEST_UUID,
            playerId = player.id or "nil",
            receivedCount = receiver.__smmlReceivedCount,
            spent = spent,
            committed = true
        } )
        return true, "ok"
    end

    runtime.emit( "carry.service.loaded", {
        result = "ok",
        resolverCount = service.resolverCount,
        testResolverId = TEST_RESOLVER_ID,
        testReceiverUuid = SCRAP_CHEST_UUID
    } )

    return service
end
