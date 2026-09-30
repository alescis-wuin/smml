-- SMML Runtime Spine laboratory runtime.
-- Internal prototype: bootstrap, lifecycle diagnostics, contracts, transport, storage and Carry hook adapter.

local RUNTIME_VERSION = "0.5.0"
local EVENT_SCHEMA = "1"
local MARKER = "[SMML-RUNTIME] EVT"

local created = false
if type( __SMML_RUNTIME ) ~= "table" or __SMML_RUNTIME.version ~= RUNTIME_VERSION then
    __SMML_RUNTIME = {
        version = RUNTIME_VERSION,
        seq = 0,
        fileLoads = 0,
        bootstrapCalls = 0,
        initCount = 0,
        initialized = false,
        runtimeId = tostring( {} ),
        contractProbeCompleted = false
    }
    created = true
end

local runtime = __SMML_RUNTIME
runtime.fileLoads = ( runtime.fileLoads or 0 ) + 1
runtime.runtimeId = runtime.runtimeId or tostring( {} )

local function escapeValue( value )
    local text = tostring( value )
    text = string.gsub( text, "%%", "%%25" )
    text = string.gsub( text, "|", "%%7C" )
    text = string.gsub( text, "=", "%%3D" )
    text = string.gsub( text, "\r", "%%0D" )
    text = string.gsub( text, "\n", "%%0A" )
    if string.len( text ) > 1400 then
        text = string.sub( text, 1, 1400 ) .. "..."
    end
    return text
end

local function emitLine( line )
    if type( sm ) == "table" and type( sm.log ) == "table" and type( sm.log.error ) == "function" then
        sm.log.error( line )
    elseif type( print ) == "function" then
        print( line )
    end
end

local function loadConfig()
    if type( pcall ) ~= "function" then
        return false, "pcall-unavailable"
    end
    local ok, result = pcall( dofile, "$SURVIVAL_DATA/Scripts/SMML/RuntimeConfig.lua" )
    if not ok then
        return false, result
    end
    return true, result
end

local configLoadOk, configLoadDetail = loadConfig()

local function config()
    if type( __SMML_RUNTIME_CONFIG ) == "table" then
        return __SMML_RUNTIME_CONFIG
    end
    return {
        enabled = false,
        role = "unconfigured",
        runId = "UNCONFIGURED"
    }
end

function runtime.emit( eventName, fields )
    runtime.seq = ( runtime.seq or 0 ) + 1
    local cfg = config()
    local parts = {
        MARKER,
        "schema=" .. EVENT_SCHEMA,
        "seq=" .. escapeValue( runtime.seq ),
        "event=" .. escapeValue( eventName ),
        "runtimeVersion=" .. escapeValue( runtime.version ),
        "runtimeId=" .. escapeValue( runtime.runtimeId ),
        "runId=" .. escapeValue( cfg.runId or "UNCONFIGURED" ),
        "role=" .. escapeValue( cfg.role or "unconfigured" ),
        "enabled=" .. escapeValue( cfg.enabled == true ),
        "fileLoads=" .. escapeValue( runtime.fileLoads ),
        "initCount=" .. escapeValue( runtime.initCount ),
        "bootstrapCalls=" .. escapeValue( runtime.bootstrapCalls ),
        "smIsHost=" .. escapeValue( type( sm ) == "table" and sm.isHost or "unknown" )
    }

    if type( fields ) == "table" then
        local keys = {}
        for key, _ in pairs( fields ) do
            keys[#keys + 1] = key
        end
        table.sort( keys, function( a, b ) return tostring( a ) < tostring( b ) end )
        for _, key in ipairs( keys ) do
            parts[#parts + 1] = escapeValue( key ) .. "=" .. escapeValue( fields[key] )
        end
    end

    emitLine( table.concat( parts, "|" ) )
end

if type( SMML ) ~= "table" then
    SMML = {}
end
SMML.runtime = runtime
SMML.diagnostics = SMML.diagnostics or {}
SMML.diagnostics.emit = runtime.emit

local function loadContractRegistry()
    if type( pcall ) ~= "function" then
        return false, "pcall-unavailable"
    end

    __SMML_CONTRACT_REGISTRY_FACTORY = nil
    local ok, loadDetail = pcall( dofile, "$SURVIVAL_DATA/Scripts/SMML/ContractRegistry.lua" )
    if not ok then
        return false, loadDetail
    end

    local factory = __SMML_CONTRACT_REGISTRY_FACTORY
    __SMML_CONTRACT_REGISTRY_FACTORY = nil
    if type( factory ) ~= "function" then
        return false, "factory-missing"
    end

    local createOk, registry = pcall( factory, runtime )
    if not createOk then
        return false, registry
    end
    if type( registry ) ~= "table" or type( registry.register ) ~= "function" or type( registry.dispatch ) ~= "function" then
        return false, "registry-invalid"
    end

    SMML.contracts = registry
    runtime.contracts = registry
    return true, "ok"
end

local contractRegistryLoadOk, contractRegistryLoadDetail = loadContractRegistry()

local function loadTransportService()
    if type( pcall ) ~= "function" then
        return false, "pcall-unavailable"
    end

    __SMML_TRANSPORT_SERVICE_FACTORY = nil
    local ok, loadDetail = pcall( dofile, "$SURVIVAL_DATA/Scripts/SMML/TransportService.lua" )
    if not ok then
        return false, loadDetail
    end

    local factory = __SMML_TRANSPORT_SERVICE_FACTORY
    __SMML_TRANSPORT_SERVICE_FACTORY = nil
    if type( factory ) ~= "function" then
        return false, "factory-missing"
    end

    local createOk, service = pcall( factory, runtime )
    if not createOk then
        return false, service
    end
    if
        type( service ) ~= "table" or
        type( service.onServerCreate ) ~= "function" or
        type( service.onClientCreate ) ~= "function" or
        type( service.onClientUpdate ) ~= "function" or
        type( service.onServerEnvelope ) ~= "function" or
        type( service.onClientReply ) ~= "function" or
        type( service.sendToServer ) ~= "function"
    then
        return false, "transport-invalid"
    end

    SMML.transport = service
    runtime.transport = service
    return true, "ok"
end

local transportLoadOk, transportLoadDetail = loadTransportService()

local function loadStorageService()
    if type( pcall ) ~= "function" then
        return false, "pcall-unavailable"
    end

    __SMML_STORAGE_SERVICE_FACTORY = nil
    local ok, loadDetail = pcall( dofile, "$SURVIVAL_DATA/Scripts/SMML/StorageService.lua" )
    if not ok then
        return false, loadDetail
    end

    local factory = __SMML_STORAGE_SERVICE_FACTORY
    __SMML_STORAGE_SERVICE_FACTORY = nil
    if type( factory ) ~= "function" then
        return false, "factory-missing"
    end

    local createOk, service = pcall( factory, runtime )
    if not createOk then
        return false, service
    end
    if type( service ) ~= "table" or type( service.onServerCreate ) ~= "function" or type( service.onServerFixedUpdate ) ~= "function" then
        return false, "storage-invalid"
    end

    SMML.storage = service
    runtime.storage = service
    return true, "ok"
end

local storageLoadOk, storageLoadDetail = loadStorageService()

local function loadCarryAdapter()
    if type( pcall ) ~= "function" then
        return false, "pcall-unavailable"
    end

    __SMML_CARRY_ADAPTER_FACTORY = nil
    local ok, loadDetail = pcall( dofile, "$SURVIVAL_DATA/Scripts/SMML/CarryAdapter.lua" )
    if not ok then
        return false, loadDetail
    end

    local factory = __SMML_CARRY_ADAPTER_FACTORY
    __SMML_CARRY_ADAPTER_FACTORY = nil
    if type( factory ) ~= "function" then
        return false, "factory-missing"
    end

    local createOk, service = pcall( factory, runtime )
    if not createOk then
        return false, service
    end
    if type( service ) ~= "table" or type( service.resolveInsertTarget ) ~= "function" or type( service.onVanillaServerRelay ) ~= "function" then
        return false, "carry-adapter-invalid"
    end

    SMML.carry = service
    runtime.carry = service
    return true, "ok"
end

local carryLoadOk, carryLoadDetail = loadCarryAdapter()

local function runContractProbe()
    if runtime.contractProbeCompleted then
        return
    end
    runtime.contractProbeCompleted = true

    if not contractRegistryLoadOk or type( runtime.contracts ) ~= "table" then
        runtime.emit( "contract.probe.complete", {
            ok = false,
            reason = contractRegistryLoadDetail
        } )
        return
    end

    local contracts = runtime.contracts
    local registeredEcho = contracts.register( "probe.echo@1", function( payload )
        if type( payload ) == "table" then
            return payload.value
        end
        return nil
    end )

    local registeredThrow = contracts.register( "probe.throw@1", function()
        local impossible = nil + 1
        return impossible
    end )

    local probeContext = { probe = true, source = "local-probe" }
    local echoOk, echoValue = contracts.dispatch( "probe.echo@1", { value = "echo-1" }, probeContext )
    local unknownOk, unknownCode = contracts.dispatch( "probe.unknown@1", {}, probeContext )
    local throwOk, throwCode = contracts.dispatch( "probe.throw@1", {}, probeContext )
    local recoveryOk, recoveryValue = contracts.dispatch( "probe.echo@1", { value = "echo-2" }, probeContext )

    local probeOk =
        registeredEcho == true and
        registeredThrow == true and
        echoOk == true and echoValue == "echo-1" and
        unknownOk == false and unknownCode == "unknown_contract" and
        throwOk == false and throwCode == "handler_error" and
        recoveryOk == true and recoveryValue == "echo-2"

    runtime.emit( "contract.probe.complete", {
        ok = probeOk,
        echoOk = echoOk,
        unknownRejected = unknownOk == false and unknownCode == "unknown_contract",
        throwIsolated = throwOk == false and throwCode == "handler_error",
        recoveryOk = recoveryOk
    } )
end

function runtime.bootstrap( source )
    runtime.bootstrapCalls = ( runtime.bootstrapCalls or 0 ) + 1
    local first = false
    if not runtime.initialized then
        runtime.initialized = true
        runtime.initCount = ( runtime.initCount or 0 ) + 1
        first = true
    end

    runtime.emit( "runtime.bootstrap", {
        source = source or "unknown",
        firstInitialization = first,
        pcallAvailable = type( pcall ) == "function",
        xpcallAvailable = type( xpcall ) == "function"
    } )

    if first and config().enabled == true then
        runContractProbe()
    end

    return first
end

function runtime.lifecycle( eventName, side, fields )
    local out = {
        side = side or "unknown"
    }
    if type( fields ) == "table" then
        for key, value in pairs( fields ) do
            out[key] = value
        end
    end
    runtime.emit( "lifecycle." .. tostring( eventName ), out )
end

runtime.emit( "runtime.file.loaded", {
    createdThisLoad = created,
    configPresent = type( __SMML_RUNTIME_CONFIG ) == "table",
    configLoadOk = configLoadOk,
    configLoadDetail = configLoadOk and "ok" or configLoadDetail,
    contractRegistryLoadOk = contractRegistryLoadOk,
    contractRegistryLoadDetail = contractRegistryLoadDetail,
    transportLoadOk = transportLoadOk,
    transportLoadDetail = transportLoadDetail,
    storageLoadOk = storageLoadOk,
    storageLoadDetail = storageLoadDetail,
    carryLoadOk = carryLoadOk,
    carryLoadDetail = carryLoadDetail
} )
