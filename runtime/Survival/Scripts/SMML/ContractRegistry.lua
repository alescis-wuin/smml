-- SMML Runtime Spine laboratory ContractRegistry.
-- Internal prototype: local registration and protected dispatch only.

__SMML_CONTRACT_REGISTRY_FACTORY = function( runtime )
    local registry = {
        handlers = {}
    }

    local function emit( eventName, fields )
        if type( runtime ) == "table" and type( runtime.emit ) == "function" then
            runtime.emit( eventName, fields )
        end
    end

    local function captureError( detail )
        return tostring( detail )
    end

    function registry.register( contractId, handler )
        if type( contractId ) ~= "string" or contractId == "" then
            emit( "contract.register", {
                contract = tostring( contractId ),
                result = "invalid_contract_id"
            } )
            return false, "invalid_contract_id"
        end

        if type( handler ) ~= "function" then
            emit( "contract.register", {
                contract = contractId,
                result = "invalid_handler"
            } )
            return false, "invalid_handler"
        end

        if registry.handlers[contractId] ~= nil then
            emit( "contract.register", {
                contract = contractId,
                result = "duplicate_contract"
            } )
            return false, "duplicate_contract"
        end

        registry.handlers[contractId] = handler
        emit( "contract.register", {
            contract = contractId,
            result = "ok"
        } )
        return true
    end

    function registry.dispatch( contractId, payload, context )
        local handler = registry.handlers[contractId]
        local contextSource = type( context ) == "table" and context.source or "unspecified"
        local requestId = type( context ) == "table" and context.requestId or "none"
        if handler == nil then
            emit( "contract.dispatch", {
                contract = tostring( contractId ),
                contextSource = contextSource,
                requestId = requestId,
                result = "unknown_contract"
            } )
            return false, "unknown_contract"
        end

        if type( xpcall ) ~= "function" then
            emit( "contract.dispatch", {
                contract = contractId,
                contextSource = contextSource,
                requestId = requestId,
                result = "protection_unavailable"
            } )
            return false, "protection_unavailable"
        end

        local ok, result = xpcall(
            function()
                return handler( payload, context )
            end,
            captureError
        )

        if not ok then
            emit( "contract.dispatch", {
                contract = contractId,
                contextSource = contextSource,
                requestId = requestId,
                result = "handler_error",
                detail = result
            } )
            return false, "handler_error"
        end

        emit( "contract.dispatch", {
            contract = contractId,
            contextSource = contextSource,
            requestId = requestId,
            result = "ok"
        } )
        return true, result
    end

    emit( "contract.registry.loaded", {
        result = "ok"
    } )

    return registry
end
