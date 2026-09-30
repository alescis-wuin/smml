-- SMML GP0 Runtime Probe v0.1.3
-- Passive instrumentation only.
-- Uses only Lua primitives already observed in vanilla scripts.

local created = false

if type( __SMML_GP0_PROBE ) ~= "table" then
    __SMML_GP0_PROBE = {
        version = "0.1.3",
        seq = 0,
        fileLoads = 0,
        initCount = 0,
        bootstrapCalls = 0,
        initialized = false,
        once = {},
        limits = {},
        counters = {}
    }
    created = true
end

local probe = __SMML_GP0_PROBE

probe.fileLoads = ( probe.fileLoads or 0 ) + 1
probe.once = probe.once or {}
probe.limits = probe.limits or {}
probe.counters = probe.counters or {}

local function clean( value )
    local text = tostring( value )
    text = string.gsub( text, "[\r\n]+", "\\n" )
    text = string.gsub( text, "|", "/" )
    if string.len( text ) > 700 then
        text = string.sub( text, 1, 700 ) .. "..."
    end
    return text
end

local function hostFlag()
    if type( sm ) == "table" and sm.isHost ~= nil then
        return tostring( sm.isHost )
    end
    return "unknown"
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
    local parts = {
        "[SMML-GP0-PROBE] EVT",
        "seq=" .. clean( probe.seq ),
        "event=" .. clean( eventName ),
        "runtime=" .. clean( probe ),
        "version=" .. clean( probe.version ),
        "fileLoads=" .. clean( probe.fileLoads ),
        "initCount=" .. clean( probe.initCount ),
        "bootstrapCalls=" .. clean( probe.bootstrapCalls ),
        "host=" .. clean( hostFlag() )
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

function probe.markLimited( key, limit, eventName, fields )
    local count = ( probe.limits[key] or 0 ) + 1
    probe.limits[key] = count
    if count <= limit then
        fields = fields or {}
        fields.limitedKey = key
        fields.limitedCount = count
        probe.mark( eventName, fields )
    end
end

function probe.count( key, amount )
    amount = amount or 1
    probe.counters[key] = ( probe.counters[key] or 0 ) + amount
    return probe.counters[key]
end

function probe.runErrorIsolation( side )
    local onceKey = "error-isolation:" .. tostring( side )
    if probe.once[onceKey] then
        probe.mark( "error_isolation_skip", { side = side, reason = "already-run" } )
        return
    end
    probe.once[onceKey] = true

    local hasPcall = type( pcall ) == "function"
    local hasXpcall = type( xpcall ) == "function"
    local hasDebugTraceback = type( debug ) == "table" and type( debug.traceback ) == "function"

    probe.mark( "lua_capabilities", {
        side = side,
        rawget = type( rawget ) == "function",
        rawset = type( rawset ) == "function",
        pcall = hasPcall,
        xpcall = hasXpcall,
        debugTraceback = hasDebugTraceback
    } )

    probe.mark( "error_isolation_begin", {
        side = side,
        hasPcall = hasPcall,
        hasXpcall = hasXpcall,
        hasDebugTraceback = hasDebugTraceback
    } )

    local order = {}

    local function handler( err )
        if hasDebugTraceback and hasPcall then
            local ok, trace = pcall( debug.traceback, tostring( err ), 2 )
            if ok then
                return trace
            end
        end
        return tostring( err )
    end

    local function run( name, fn )
        order[#order + 1] = name
        local ok = false
        local result = "no-protected-call"

        if hasXpcall then
            ok, result = xpcall( fn, handler )
        elseif hasPcall then
            ok, result = pcall( fn )
        else
            probe.mark( "error_isolation_unavailable", { side = side, handler = name } )
            return
        end

        probe.mark( "error_isolation_handler", {
            side = side,
            handler = name,
            mode = hasXpcall and "xpcall" or "pcall",
            ok = ok,
            result = result
        } )
    end

    if hasXpcall or hasPcall then
        run( "A", function() return "A_OK" end )
        run( "B", function() error( "SMML_GP0_INTENTIONAL_ERROR" ) end )
        run( "C", function() return "C_OK" end )
    end

    probe.mark( "error_isolation_end", {
        side = side,
        order = table.concat( order, "," ),
        continuedAfterError = order[3] == "C",
        mode = hasXpcall and "xpcall" or ( hasPcall and "pcall" or "none" )
    } )
end

probe.mark( "runtime_file_evaluated", {
    createdThisLoad = created,
    rawgetAvailable = type( rawget ) == "function",
    rawsetAvailable = type( rawset ) == "function",
    pcallAvailable = type( pcall ) == "function",
    xpcallAvailable = type( xpcall ) == "function",
    debugTracebackAvailable = type( debug ) == "table" and type( debug.traceback ) == "function"
} )
