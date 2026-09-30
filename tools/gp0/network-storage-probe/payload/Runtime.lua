-- SMML GP0.5 Network / Storage Probe v0.2.0
-- Temporary research runtime. Fail-open, minimal and self-contained.

local created = false
if type( __SMML_GP0_NS ) ~= "table" or __SMML_GP0_NS.version ~= "0.2.0" then
    __SMML_GP0_NS = {
        version = "0.2.0",
        seq = 0,
        fileLoads = 0,
        initCount = 0,
        bootstrapCalls = 0,
        initialized = false,
        once = {},
        counters = {},
        runtimeId = tostring( {} )
    }
    created = true
end

local probe = __SMML_GP0_NS
probe.fileLoads = ( probe.fileLoads or 0 ) + 1
probe.once = probe.once or {}
probe.counters = probe.counters or {}
probe.runtimeId = probe.runtimeId or tostring( {} )

local function clean( value )
    local text = tostring( value )
    text = string.gsub( text, "[\r\n]+", "\\n" )
    text = string.gsub( text, "|", "/" )
    if string.len( text ) > 1400 then
        text = string.sub( text, 1, 1400 ) .. "..."
    end
    return text
end

local function emit( line )
    if type( sm ) == "table" and type( sm.log ) == "table" and type( sm.log.error ) == "function" then
        sm.log.error( line )
    elseif type( print ) == "function" then
        print( line )
    end
end

function probe.mark( eventName, fields )
    probe.seq = ( probe.seq or 0 ) + 1
    local config = type( __SMML_GP0_NS_CONFIG ) == "table" and __SMML_GP0_NS_CONFIG or {}
    local parts = {
        "[SMML-GP0-NS] EVT",
        "seq=" .. clean( probe.seq ),
        "event=" .. clean( eventName ),
        "version=" .. clean( probe.version ),
        "runtimeId=" .. clean( probe.runtimeId ),
        "runId=" .. clean( config.runId or "UNCONFIGURED" ),
        "role=" .. clean( config.role or "disabled" ),
        "fileLoads=" .. clean( probe.fileLoads ),
        "initCount=" .. clean( probe.initCount ),
        "bootstrapCalls=" .. clean( probe.bootstrapCalls ),
        "smIsHost=" .. clean( type( sm ) == "table" and sm.isHost or "unknown" )
    }

    if type( fields ) == "table" then
        local keys = {}
        for key, _ in pairs( fields ) do
            keys[#keys + 1] = key
        end
        table.sort( keys, function( a, b ) return tostring( a ) < tostring( b ) end )
        for _, key in ipairs( keys ) do
            parts[#parts + 1] = clean( key ) .. "=" .. clean( fields[key] )
        end
    end

    emit( table.concat( parts, "|" ) )
end

function probe.bootstrap( source )
    probe.bootstrapCalls = ( probe.bootstrapCalls or 0 ) + 1
    local first = false
    if not probe.initialized then
        probe.initialized = true
        probe.initCount = ( probe.initCount or 0 ) + 1
        first = true
    end
    probe.mark( "bootstrap", {
        source = source,
        firstInitialization = first,
        createdThisLoad = created
    } )
    return first
end

function probe.count( key, amount )
    amount = amount or 1
    probe.counters[key] = ( probe.counters[key] or 0 ) + amount
    return probe.counters[key]
end

local function protectedDofile( path, label )
    if type( pcall ) ~= "function" then
        probe.mark( "runtime.load.error", { component = label, reason = "pcall-unavailable", path = path } )
        return false
    end
    local ok, result = pcall( dofile, path )
    if not ok then
        probe.mark( "runtime.load.error", { component = label, reason = result, path = path } )
        return false
    end
    probe.mark( "runtime.load.ok", { component = label, path = path } )
    return true
end

protectedDofile( "$SURVIVAL_DATA/Scripts/SMMLProbeNS/ProbeConfig.lua", "config" )
protectedDofile( "$SURVIVAL_DATA/Scripts/SMMLProbeNS/Probe.lua", "probe" )

local config = type( __SMML_GP0_NS_CONFIG ) == "table" and __SMML_GP0_NS_CONFIG or {}
probe.mark( "runtime.ready", {
    createdThisLoad = created,
    pcallAvailable = type( pcall ) == "function",
    xpcallAvailable = type( xpcall ) == "function",
    rawgetAvailable = type( rawget ) == "function",
    debugTracebackAvailable = type( debug ) == "table" and type( debug.traceback ) == "function",
    enabled = config.enabled == true,
    configuredRole = config.role or "disabled"
} )
