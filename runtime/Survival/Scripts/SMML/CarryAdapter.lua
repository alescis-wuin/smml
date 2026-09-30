-- SMML Runtime Spine laboratory Carry adapter.
-- v0.5.0: empty resolver path + vanilla relay observation only.

__SMML_CARRY_ADAPTER_FACTORY = function( runtime )
    local service = {
        resolverCount = 0
    }

    local function safeUuid( value )
        if value == nil then
            return "nil"
        end
        return tostring( value )
    end

    function service.resolveInsertTarget( context )
        if type( context ) ~= "table" then
            return false, "invalid_context"
        end

        if context.isStart == true then
            runtime.emit( "carry.resolve.empty", {
                carryUuid = safeUuid( context.carryUuid ),
                raycastSuccess = context.raycastSuccess == true,
                resultType = context.resultType or "nil",
                resolverCount = service.resolverCount
            } )
        end

        return false, "no_resolver"
    end

    function service.onVanillaServerRelay( params, player )
        runtime.emit( "carry.vanilla.rpc.server", {
            carryUuid = params and params.itemA or "nil",
            targetUuid = params and params.targetShape and params.targetShape:getShapeUuid() or "nil",
            playerId = player and player.id or "nil"
        } )
        return true
    end

    runtime.emit( "carry.service.loaded", {
        result = "ok",
        resolverCount = service.resolverCount
    } )

    return service
end
