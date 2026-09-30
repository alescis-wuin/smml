-- SMML Runtime Spine laboratory StorageService.
-- Internal prototype: server-only sm.storage lifecycle, logical namespace and migration probe.

__SMML_STORAGE_SERVICE_FACTORY = function( runtime )
    local storage = {
        serverGame = nil,
        serverTicks = 0,
        phaseDone = false
    }

    local STORAGE_PREFIX = "SMML_RUNTIME_STORAGE_V040_"

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

    local function enabledHost()
        local cfg = config()
        return cfg.enabled == true and cfg.role == "host" and type( cfg.runId ) == "string"
    end

    local function storageKey()
        return STORAGE_PREFIX .. tostring( config().runId )
    end

    local function backendAvailable()
        return
            type( sm ) == "table" and
            type( sm.storage ) == "table" and
            type( sm.storage.load ) == "function" and
            type( sm.storage.save ) == "function"
    end

    local function validateLogicalNamespaces( root )
        if type( root ) ~= "table" or type( root.namespaces ) ~= "table" then
            return false, "namespaces_missing"
        end
        local a = root.namespaces["com.smml.probe.a"]
        local b = root.namespaces["com.smml.probe.b"]
        if type( a ) ~= "table" or type( b ) ~= "table" then
            return false, "fake_mod_namespace_missing"
        end
        if a.sharedKey ~= "A" or b.sharedKey ~= "B" then
            return false, "shared_key_value_mismatch"
        end
        if a.sharedKey == b.sharedKey then
            return false, "logical_isolation_collision"
        end
        return true, "ok"
    end

    local function complete( phase, ok, detail )
        emit( "storage.probe.complete", {
            phase = phase,
            ok = ok == true,
            detail = detail or "ok"
        } )
    end

    local function saveRoot( key, value, eventName )
        local ok, detail = pcall( function()
            sm.storage.save( key, value )
        end )
        local namespaceOk = false
        if type( value ) == "table" then
            namespaceOk = select( 1, validateLogicalNamespaces( value ) ) == true
        end
        emit( ok and eventName or "storage.save.error", {
            key = key,
            schemaVersion = type( value ) == "table" and value.schemaVersion or "nil",
            namespaceIsolation = namespaceOk,
            detail = ok and "ok" or detail
        } )
        return ok
    end

    local function runPhase()
        if not enabledHost() then
            return
        end
        if not backendAvailable() then
            emit( "storage.error", { reason = "storage_unavailable" } )
            complete( "backend_unavailable", false, "storage_unavailable" )
            return
        end

        local key = storageKey()
        local loadOk, stored = pcall( sm.storage.load, key )
        if not loadOk then
            emit( "storage.load.error", { key = key, detail = stored } )
            complete( "load_error", false, stored )
            return
        end

        if stored == nil then
            emit( "storage.load.absent", { key = key } )
            local schema1 = {
                marker = "SMML_RUNTIME_STORAGE",
                runId = config().runId,
                schemaVersion = 1,
                namespaces = {
                    ["com.smml.probe.a"] = { sharedKey = "A", dataKey = "shared" },
                    ["com.smml.probe.b"] = { sharedKey = "B", dataKey = "shared" }
                }
            }
            local namespaceOk, namespaceDetail = validateLogicalNamespaces( schema1 )
            emit( "storage.namespace.check", {
                phase = "schema1_before_save",
                success = namespaceOk,
                detail = namespaceDetail,
                schemaVersion = 1
            } )
            local saved = saveRoot( key, schema1, "storage.save.schema1" )
            complete( "schema1_saved", namespaceOk and saved, namespaceDetail )
            return
        end

        if type( stored ) ~= "table" then
            emit( "storage.load.foreign", { key = key, storedType = type( stored ) } )
            complete( "foreign_value", false, "stored_value_not_table" )
            return
        end

        local namespaceOk, namespaceDetail = validateLogicalNamespaces( stored )
        emit( "storage.namespace.check", {
            phase = "load",
            success = namespaceOk,
            detail = namespaceDetail,
            schemaVersion = stored.schemaVersion or "nil"
        } )

        if stored.marker ~= "SMML_RUNTIME_STORAGE" or stored.runId ~= config().runId then
            emit( "storage.load.foreign", {
                key = key,
                marker = stored.marker or "nil",
                storedRunId = stored.runId or "nil",
                schemaVersion = stored.schemaVersion or "nil"
            } )
            complete( "foreign_document", false, "marker_or_run_mismatch" )
            return
        end

        if stored.schemaVersion == 1 then
            emit( "storage.load.schema1", {
                key = key,
                namespaceIsolation = namespaceOk
            } )
            local schema2 = {
                marker = stored.marker,
                runId = stored.runId,
                schemaVersion = 2,
                migratedFrom = 1,
                namespaces = stored.namespaces,
                migration = { completed = true, source = "runtime-spine-v0.4" }
            }
            local namespaceOk2, namespaceDetail2 = validateLogicalNamespaces( schema2 )
            emit( "storage.migration.1to2", {
                success = namespaceOk2,
                detail = namespaceDetail2
            } )
            local saved = saveRoot( key, schema2, "storage.save.schema2" )
            complete( "schema2_migrated", namespaceOk and namespaceOk2 and saved, namespaceDetail2 )
            return
        end

        if stored.schemaVersion == 2 then
            emit( "storage.load.schema2", {
                key = key,
                migratedFrom = stored.migratedFrom or "nil",
                namespaceIsolation = namespaceOk
            } )
            complete( "schema2_stable", namespaceOk and stored.migratedFrom == 1, namespaceDetail )
            return
        end

        emit( "storage.load.unknown_schema", {
            key = key,
            schemaVersion = stored.schemaVersion or "nil"
        } )
        complete( "unknown_schema", false, tostring( stored.schemaVersion ) )
    end

    function storage.onServerCreate( game )
        storage.serverGame = game
        storage.serverTicks = 0
        storage.phaseDone = false
        emit( "storage.server.bound", { result = game ~= nil and "ok" or "missing_game" } )
    end

    function storage.onServerFixedUpdate( game, timeStep )
        if not enabledHost() or storage.phaseDone then
            return
        end
        if storage.serverGame == nil then
            storage.serverGame = game
        end
        storage.serverTicks = ( storage.serverTicks or 0 ) + 1
        if storage.serverTicks < 1 then
            return
        end
        storage.phaseDone = true
        local ok, detail = pcall( runPhase )
        if not ok then
            emit( "storage.phase.error", { detail = detail } )
            complete( "phase_error", false, detail )
        end
    end

    emit( "storage.service.loaded", { result = "ok" } )
    return storage
end
