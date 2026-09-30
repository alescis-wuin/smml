-- SMML GP0.2 Carry / Storage Laboratory v0.1.4
-- Server-authoritative orchestration. No direct save-file access.

if type( __SMML_GP0_PROBE ) ~= "table" then
    return
end

local probe = __SMML_GP0_PROBE
local config = type( __SMML_GP0_LAB_CONFIG ) == "table" and __SMML_GP0_LAB_CONFIG or { enabled = false }
local data = type( SMML_GP0_LAB_DATA ) == "table" and SMML_GP0_LAB_DATA or nil

local lab = probe.lab or {}
probe.lab = lab
lab.state = lab.state or {
    stage = "disabled",
    player = nil,
    game = nil,
    fixtures = {},
    fixtureIndex = 1,
    itemIndex = 1,
    readyTicks = 0,
    carryTarget = nil,
    carryReceiveSeen = false,
    carryRpcSeen = false,
    started = false,
    completed = false
}

local state = lab.state

local function enabled()
    return config.enabled == true and data ~= nil
end

local function exists( object )
    if object == nil then
        return false
    end
    if type( sm ) == "table" and type( sm.exists ) == "function" then
        return sm.exists( object )
    end
    return true
end

local function uuid( text )
    return sm.uuid.new( text )
end

local function notify( text )
    if state.game and state.player and state.game.network and type( pcall ) == "function" then
        local ok, err = pcall( function() state.game.network:sendToClient( state.player, "cl_smmlGp0LabMessage", { text = text } ) end )
        if not ok then
            probe.mark( "lab.notify.error", { text = text, detail = err } )
        end
    end
    probe.mark( "lab.notify", { text = text } )
end

local function getPlayerCharacter()
    if state.player and exists( state.player ) and state.player.character and exists( state.player.character ) then
        return state.player.character
    end
    return nil
end

local function getBasis()
    local character = getPlayerCharacter()
    if not character then
        return nil, nil, nil
    end
    local forward = character:getDirection()
    forward = sm.vec3.new( forward.x, forward.y, 0 ):safeNormalize( sm.vec3.new( 0, 1, 0 ) )
    local right = sm.vec3.new( forward.y, -forward.x, 0 )
    return character.worldPosition, forward, right
end

local function fixturePosition( index )
    local origin, forward, right = getBasis()
    if not origin then
        return nil
    end
    local zero = index - 1
    local row = math.floor( zero / 4 )
    local col = zero - row * 4
    local lateral = ( col - 1.5 ) * 3.2
    local distance = 6.0 + row * 3.2
    return origin + forward * distance + right * lateral + sm.vec3.new( 0, 0, 1.0 )
end

local function createPart( uuidText, position )
    local character = getPlayerCharacter()
    if not character or not position then
        return nil
    end
    local world = character:getWorld()
    if type( pcall ) ~= "function" then
        return nil
    end
    local ok, shape = pcall( sm.shape.createPart, uuid( uuidText ), position, sm.quat.identity(), false, true, world )
    if not ok then
        probe.mark( "fixture.create.error", { uuid = uuidText, detail = shape } )
        return nil
    end
    return shape
end

local function getContainerFromShape( shape )
    if not exists( shape ) then
        return nil
    end
    local interactable = shape:getInteractable()
    if not interactable then
        return nil
    end
    return interactable:getContainer( 0 )
end

local function spawnStorageFixtures()
    state.fixtures = {}
    for index, fixture in ipairs( data.storageFixtures ) do
        local position = fixturePosition( index )
        local shape = createPart( fixture.uuid, position )
        state.fixtures[index] = { spec = fixture, shape = shape, ready = false }
        probe.mark( "storage.fixture.created", {
            fixtureIndex = index,
            fixtureId = fixture.id,
            fixtureTitle = fixture.title,
            fixtureUuid = fixture.uuid,
            created = shape ~= nil
        } )
    end
    state.readyTicks = 0
    state.stage = "wait_storage"
end

local function safeRevision( container )
    if type( pcall ) ~= "function" then
        return "unavailable"
    end
    local ok, value = pcall( function() return container:getRevision() end )
    if ok then
        return value
    end
    return "unavailable"
end

local function pollStorageReady()
    state.readyTicks = state.readyTicks + 1
    local allReady = true
    for index, fixtureState in ipairs( state.fixtures ) do
        if not fixtureState.ready then
            local container = getContainerFromShape( fixtureState.shape )
            if container then
                fixtureState.container = container
                fixtureState.ready = true
                probe.mark( "storage.fixture.ready", {
                    fixtureIndex = index,
                    fixtureId = fixtureState.spec.id,
                    fixtureUuid = fixtureState.spec.uuid,
                    expectedSlots = fixtureState.spec.slots,
                    actualSlots = container:getSize(),
                    revision = safeRevision( container )
                } )
            else
                allReady = false
            end
        end
    end

    if allReady then
        state.fixtureIndex = 1
        state.itemIndex = 1
        state.stage = "storage_matrix"
        notify( "GP0: conteneurs prets; matrice stockage automatique en cours." )
    elseif state.readyTicks >= 240 then
        probe.mark( "storage.fixture.timeout", { ticks = state.readyTicks } )
        state.fixtureIndex = 1
        state.itemIndex = 1
        state.stage = "storage_matrix"
        notify( "GP0: certains conteneurs ne sont pas prets; poursuite avec diagnostic partiel." )
    end
end

local function boolText( value )
    return value == true and "true" or "false"
end

local function runStorageCase( fixtureState, item )
    local fixture = fixtureState.spec
    local container = fixtureState.container or getContainerFromShape( fixtureState.shape )
    if not container then
        probe.mark( "storage.case", {
            fixtureId = fixture.id,
            fixtureTitle = fixture.title,
            fixtureUuid = fixture.uuid,
            expectedSlots = fixture.slots,
            itemId = item.id,
            itemTitle = item.title,
            itemUuid = item.uuid,
            ready = false,
            canCollect = false,
            dryRunCollected = 0,
            unchangedAfterAbort = true,
            error = "container-unavailable"
        } )
        return
    end

    local itemUuid = uuid( item.uuid )
    local beforeQuantity = sm.container.totalQuantity( container, itemUuid )
    local beforeRevision = safeRevision( container )
    local canCollect = sm.container.canCollect( container, itemUuid, 1 )
    local beginOk = sm.container.beginTransaction()
    local collected = 0
    local abortOk = false
    if beginOk then
        collected = sm.container.collect( container, itemUuid, 1, false )
        sm.container.abortTransaction()
        abortOk = true
    end
    local afterQuantity = sm.container.totalQuantity( container, itemUuid )
    local afterRevision = safeRevision( container )

    probe.mark( "storage.case", {
        fixtureId = fixture.id,
        fixtureTitle = fixture.title,
        fixtureUuid = fixture.uuid,
        expectedSlots = fixture.slots,
        actualSlots = container:getSize(),
        itemId = item.id,
        itemTitle = item.title,
        itemUuid = item.uuid,
        ready = true,
        canCollect = boolText( canCollect ),
        beginTransaction = boolText( beginOk ),
        dryRunCollected = collected,
        abortIssued = boolText( abortOk ),
        beforeQuantity = beforeQuantity,
        afterQuantity = afterQuantity,
        unchangedAfterAbort = boolText( beforeQuantity == afterQuantity ),
        revisionBefore = beforeRevision,
        revisionAfter = afterRevision
    } )
end

local function storageMatrixTick()
    local budget = 4
    while budget > 0 and state.fixtureIndex <= #state.fixtures do
        local fixtureState = state.fixtures[state.fixtureIndex]
        local item = data.storageItems[state.itemIndex]
        local ok, err = pcall( runStorageCase, fixtureState, item )
        if not ok then
            probe.mark( "storage.case", {
                fixtureId = fixtureState.spec.id,
                fixtureTitle = fixtureState.spec.title,
                fixtureUuid = fixtureState.spec.uuid,
                expectedSlots = fixtureState.spec.slots,
                itemId = item.id,
                itemTitle = item.title,
                itemUuid = item.uuid,
                ready = fixtureState.ready == true,
                canCollect = false,
                dryRunCollected = 0,
                unchangedAfterAbort = "unknown",
                error = err
            } )
        end

        state.itemIndex = state.itemIndex + 1
        if state.itemIndex > #data.storageItems then
            state.itemIndex = 1
            state.fixtureIndex = state.fixtureIndex + 1
        end
        budget = budget - 1
    end

    if state.fixtureIndex > #state.fixtures then
        state.stage = "loadout"
        probe.mark( "storage.matrix.complete", {
            fixtures = #data.storageFixtures,
            items = #data.storageItems,
            cases = #data.storageFixtures * #data.storageItems
        } )
        notify( "GP0: matrice stockage terminee. Les 16 conteneurs restent places pour verification visuelle." )
    end
end

local function countFreeSlots( inventory )
    local free = 0
    for slot = 0, inventory:getSize() - 1 do
        local item = inventory:getItem( slot )
        if item.uuid:isNil() or item.quantity == 0 then
            free = free + 1
        end
    end
    return free
end

local function injectManualLoadout()
    if config.manualLoadout == false then
        probe.mark( "loadout.skipped", { reason = "disabled" } )
        state.stage = "spawn_carry"
        return
    end

    local inventory = state.player:getInventory()
    probe.mark( "loadout.begin", {
        inventorySize = inventory:getSize(),
        freeSlots = countFreeSlots( inventory )
    } )

    for _, item in ipairs( data.storageItems ) do
        local desired = item.manualQty or 0
        if desired > 0 then
            local ok, err = pcall( function()
                local itemUuid = uuid( item.uuid )
                local before = sm.container.totalQuantity( inventory, itemUuid )
                local beginOk = sm.container.beginTransaction()
                local collected = 0
                local commit = false
                if beginOk then
                    collected = sm.container.collect( inventory, itemUuid, desired, false )
                    commit = sm.container.endTransaction()
                end
                local after = sm.container.totalQuantity( inventory, itemUuid )
                probe.mark( "loadout.item", {
                    itemId = item.id,
                    itemTitle = item.title,
                    itemUuid = item.uuid,
                    desired = desired,
                    collectedRequestedByApi = collected,
                    commit = boolText( commit ),
                    before = before,
                    after = after,
                    delta = after - before
                } )
            end )
            if not ok then
                probe.mark( "loadout.item", { itemId = item.id, itemTitle = item.title, itemUuid = item.uuid, desired = desired, error = err } )
            end
        end
    end

    probe.mark( "loadout.complete", {
        inventorySize = inventory:getSize(),
        freeSlots = countFreeSlots( inventory )
    } )
    state.stage = "spawn_carry"
end

local function spawnCarryFixture()
    local origin, forward, right = getBasis()
    if not origin then
        return
    end
    local position = origin + forward * 3.0 + right * 0.0 + sm.vec3.new( 0, 0, 1.0 )
    state.carryTarget = createPart( data.carry.targetUuid, position )
    if state.carryTarget then
        state.carryTarget:setColor( sm.color.new( 0.2, 1.0, 0.2 ) )
    end
    state.readyTicks = 0
    state.stage = "wait_carry_target"
    probe.mark( "carry.fixture.created", {
        targetId = data.carry.targetId,
        targetTitle = data.carry.targetTitle,
        targetUuid = data.carry.targetUuid,
        created = state.carryTarget ~= nil
    } )
end

local function waitCarryTarget()
    state.readyTicks = state.readyTicks + 1
    local container = getContainerFromShape( state.carryTarget )
    if container then
        state.carryTargetContainer = container
        probe.mark( "carry.fixture.ready", {
            targetId = data.carry.targetId,
            targetUuid = data.carry.targetUuid,
            slots = container:getSize()
        } )
        state.stage = "load_carry"
    elseif state.readyTicks >= 240 then
        probe.mark( "carry.fixture.timeout", { targetUuid = data.carry.targetUuid } )
        notify( "GP0: Resource Collector non initialise; quittez le jeu et collectez les logs." )
        state.stage = "failed"
    end
end

local function loadCarry()
    local carry = state.player:getCarry()
    if not carry:isEmpty() then
        probe.mark( "carry.load.blocked", { reason = "carry-not-empty", carrySize = carry:getSize() } )
        notify( "GP0: videz ce que vous portez puis relancez le monde de test." )
        state.stage = "failed"
        return
    end

    local itemUuid = uuid( data.carry.itemUuid )
    local beginOk = sm.container.beginTransaction()
    local collected = 0
    local commit = false
    if beginOk then
        collected = sm.container.collect( carry, itemUuid, 1, false )
        commit = sm.container.endTransaction()
    end
    if commit and sm.container.totalQuantity( carry, itemUuid ) >= 1 then
        state.player:setCarryColor( sm.item.getShapeDefaultColor( itemUuid ) )
        probe.mark( "carry.loaded", {
            itemId = data.carry.itemId,
            itemTitle = data.carry.itemTitle,
            itemUuid = data.carry.itemUuid,
            collected = collected,
            commit = true
        } )
        notify( "GP0: Carry pret. Visez le Resource Collector VERT devant vous et appuyez une fois sur Inserer." )
        state.stage = "wait_carry_insert"
    else
        probe.mark( "carry.load.failed", {
            itemUuid = data.carry.itemUuid,
            beginTransaction = boolText( beginOk ),
            collected = collected,
            commit = boolText( commit )
        } )
        notify( "GP0: impossible de charger Scrap Wood dans le Carry; collectez les logs." )
        state.stage = "failed"
    end
end

local function checkCarryCompletion()
    local carry = state.player:getCarry()
    local itemUuid = uuid( data.carry.itemUuid )
    local carryQty = sm.container.totalQuantity( carry, itemUuid )
    local targetQty = state.carryTargetContainer and sm.container.totalQuantity( state.carryTargetContainer, itemUuid ) or 0

    if state.carryReceiveSeen and carryQty == 0 and targetQty >= 1 then
        state.completed = true
        state.stage = "complete"
        probe.mark( "carry.case", {
            targetId = data.carry.targetId,
            targetTitle = data.carry.targetTitle,
            targetUuid = data.carry.targetUuid,
            itemId = data.carry.itemId,
            itemTitle = data.carry.itemTitle,
            itemUuid = data.carry.itemUuid,
            rpcSeen = boolText( state.carryRpcSeen ),
            receiveSeen = boolText( state.carryReceiveSeen ),
            carryQuantity = carryQty,
            targetQuantity = targetQty,
            success = true
        } )
        notify( "GP0: test Carry valide. Vous pouvez verifier quelques coffres puis quitter proprement le jeu." )
    end
end

function lab.onGameCreate( game )
    state.game = game
    if enabled() then
        probe.mark( "lab.game.create", { runId = config.runId or "unknown" } )
    end
end

function lab.onPlayerJoined( game, player, newPlayer )
    state.game = game
    if not enabled() then
        return
    end
    if not state.player then
        state.player = player
    end
    probe.mark( "lab.player.joined", {
        playerId = player.id,
        newPlayer = boolText( newPlayer ),
        runId = config.runId or "unknown"
    } )
end

function lab.onCarryRpc( params, player )
    if not enabled() then
        return
    end
    state.carryRpcSeen = true
end

function lab.onResourceReceive( receiver, params )
    if not enabled() then
        return
    end
    state.carryReceiveSeen = true
end

function lab.tick( game, timeStep )
    if not enabled() then
        return
    end
    state.game = game

    if state.completed or state.stage == "failed" then
        return
    end

    local character = getPlayerCharacter()
    if not character then
        return
    end

    if not state.started then
        state.started = true
        state.stage = "spawn_storage"
        probe.mark( "lab.start", {
            runId = config.runId or "unknown",
            manualLoadout = boolText( config.manualLoadout ~= false ),
            playerId = state.player.id,
            world = character:getWorld()
        } )
        notify( "GP0: laboratoire arme. Creation des fixtures et tests automatiques." )
    end

    if state.stage == "spawn_storage" then
        spawnStorageFixtures()
    elseif state.stage == "wait_storage" then
        pollStorageReady()
    elseif state.stage == "storage_matrix" then
        storageMatrixTick()
    elseif state.stage == "loadout" then
        injectManualLoadout()
    elseif state.stage == "spawn_carry" then
        spawnCarryFixture()
    elseif state.stage == "wait_carry_target" then
        waitCarryTarget()
    elseif state.stage == "load_carry" then
        loadCarry()
    elseif state.stage == "wait_carry_insert" then
        checkCarryCompletion()
    end
end
