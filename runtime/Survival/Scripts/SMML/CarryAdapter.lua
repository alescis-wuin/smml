-- SMML Runtime Spine laboratory Carry adapter.
-- v0.5.1: one real resolver that maps a proxy shape on the same body to a Resource Collector.

__SMML_CARRY_ADAPTER_FACTORY = function( runtime )
    local SCRAP_WOOD_UUID = "968de65c-75f3-471b-954e-6165a4b6d3d6"
    local RESOURCE_COLLECTOR_UUID = "a930a42f-63ed-4fb0-933e-56ce8a889cc5"
    local TEST_RESOLVER_ID = "probe.resourceCollectorProxy@1"

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

    local function proxyResourceCollectorResolver( context )
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
        if safeUuid( hitShape:getShapeUuid() ) == RESOURCE_COLLECTOR_UUID then
            return nil, "vanilla_target"
        end

        local body = hitShape:getBody()
        if body == nil then
            return nil, "body_missing"
        end

        local matches = {}
        for _, shape in ipairs( body:getShapes() ) do
            if safeUuid( shape:getShapeUuid() ) == RESOURCE_COLLECTOR_UUID then
                matches[#matches + 1] = shape
            end
        end

        if #matches == 0 then
            return nil, "resource_collector_missing"
        end
        if #matches > 1 then
            return nil, "ambiguous_resource_collector"
        end

        return matches[1], "ok"
    end

    service.registerResolver( TEST_RESOLVER_ID, proxyResourceCollectorResolver )

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

    runtime.emit( "carry.service.loaded", {
        result = "ok",
        resolverCount = service.resolverCount,
        testResolverId = TEST_RESOLVER_ID
    } )

    return service
end
