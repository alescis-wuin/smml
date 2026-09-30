-- SMML GP0.2 Carry / Storage Laboratory data v0.1.4
-- Derived from the 1.0.6.889 corpus. UUID strings are intentionally explicit.

SMML_GP0_LAB_DATA = {
    storageFixtures = {
        { id = "scrap_chest", title = "Scrap Chest", uuid = "7527cf2e-1705-4214-9d07-3dc374957e25", slots = 10 },
        { id = "small_chest", title = "Small Chest", uuid = "4c474cff-3f6a-4306-93d1-c4c74578afd2", slots = 10 },
        { id = "chest", title = "Chest", uuid = "fcfae5e2-1df9-47d8-bb9a-30bec9b5b1f5", slots = 20 },
        { id = "large_chest", title = "Large Chest", uuid = "ad35f7e6-af8f-40fa-aef4-77d827ac8a8a", slots = 30 },
        { id = "xxl_chest", title = "XXL Chest", uuid = "9601f2ca-9552-48b0-afc1-b0f200461114", slots = 100 },
        { id = "locker", title = "Locker", uuid = "d0afb527-e786-4a22-a907-6da7e7cba8cb", slots = 4 },
        { id = "file_cabinet", title = "File Cabinet", uuid = "90dbaebf-8ea1-4a5a-8f6f-86ddde77c6c8", slots = 2 },
        { id = "broken_microwave", title = "Broken Microwave", uuid = "d4e6c84c-a493-44b1-81aa-4f4741ea3ed8", slots = 1 },
        { id = "fridge", title = "Fridge", uuid = "f08d772f-9851-400f-a014-d847900458a7", slots = 20 },
        { id = "gas_container", title = "Gas Container", uuid = "056e5ff1-f030-40df-946a-b830bf494c92", slots = 5 },
        { id = "water_container", title = "Water Container", uuid = "ea10d1af-b97a-46fb-8895-dfd1becb53bb", slots = 5 },
        { id = "battery_container", title = "Battery Container", uuid = "da4833fd-f981-4e08-a9f7-48e630a7c146", slots = 5 },
        { id = "ammo_container", title = "Potato Ammo Container", uuid = "096d4daf-639e-4947-a1a6-1890eaa94464", slots = 5 },
        { id = "fertilizer_container", title = "Fertilizer Container", uuid = "76331bbf-abbd-4b8d-bb54-f721a5b6193b", slots = 5 },
        { id = "seed_container", title = "Seed Container", uuid = "38ec258d-c644-4f08-8635-3f7434c884dd", slots = 5 },
        { id = "chemical_container", title = "Chemical Container", uuid = "be29592a-ef58-4b1d-b18c-895023abd27f", slots = 5 }
    },

    storageItems = {
        { id = "battery", title = "Battery", uuid = "910a7f2c-52b0-46eb-8873-ad13255539af", manualQty = 16 },
        { id = "gasoline", title = "Gasoline", uuid = "d4d68946-aa03-4b8f-b1af-96b81ad4e305", manualQty = 16 },
        { id = "water", title = "Water", uuid = "869d4736-289a-4952-96cd-8a40117a2d28", manualQty = 16 },
        { id = "potato", title = "Potato", uuid = "bfcfac34-db0f-42d6-bd0c-74a7a5c95e82", manualQty = 16 },
        { id = "fertilizer", title = "Fertilizer", uuid = "ac0b5b0a-14e1-4b31-8944-0a351fbfcc67", manualQty = 16 },
        { id = "chemical", title = "Chemical", uuid = "f74c2891-79a9-45e0-982e-4896651c2e25", manualQty = 16 },
        { id = "potato_seed", title = "Potato Seed", uuid = "eb1ef696-5c05-4662-9e47-fe1e0875ff84", manualQty = 16 },
        { id = "component_kit", title = "Component Kit", uuid = "5530e6a0-4748-4926-b134-50ca9ecb9dcf", manualQty = 16 },
        { id = "scrap_wood_block", title = "Scrap Wood Block", uuid = "1fc74a28-addb-451a-878d-c3c605d63811", manualQty = 16 },
        { id = "scrap_wheel", title = "Scrap Wheel", uuid = "59f6951a-a450-42bf-ad03-54567cb70245", manualQty = 5 },
        { id = "connect_tool", title = "Connect Tool", uuid = "8c7efc37-cd7c-4262-976e-39585f8527bf", manualQty = 1 },
        { id = "sledgehammer", title = "Sledgehammer", uuid = "bb641a4f-e391-441c-bc6d-0ae21a069476", manualQty = 0 },
        { id = "lift", title = "Lift", uuid = "8f190ce2-3a59-423e-8483-a7aa67bd5bc0", manualQty = 0 }
    },

    carry = {
        targetId = "resource_collector",
        targetTitle = "Resource Collector",
        targetUuid = "a930a42f-63ed-4fb0-933e-56ce8a889cc5",
        itemId = "scrap_wood",
        itemTitle = "Scrap Wood",
        itemUuid = "968de65c-75f3-471b-954e-6165a4b6d3d6"
    }
}

return SMML_GP0_LAB_DATA
