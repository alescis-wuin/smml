from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "gp1" / "runtime-spine-lab" / "smml_runtime_spine_lab.py"

spec = importlib.util.spec_from_file_location("smml_runtime_spine_lab", MODULE_PATH)
assert spec is not None and spec.loader is not None
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class RuntimeSpineLabTests(unittest.TestCase):
    def test_event_parser_decodes_reserved_characters(self) -> None:
        line = (
            "prefix [SMML-RUNTIME] EVT|schema=1|event=test|runId=R1|"
            "value=a%7Cb%3Dc%250A"
        )
        parsed = lab.parse_event_line(line)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["event"], "test")
        self.assertEqual(parsed["runId"], "R1")
        self.assertEqual(parsed["value"], "a|b=c%0A")

    def test_survival_player_patch_is_prefix_only(self) -> None:
        original = b'dofile( "$GAME_DATA/Scripts/game/BasePlayer.lua" )\nSurvivalPlayer = class( BasePlayer )\n'
        patched = lab.patch_survival_player(original).decode("utf-8")
        self.assertIn("SMML_RUNTIME_SPINE_BEGIN:bootstrap:SurvivalPlayer.lua", patched)
        self.assertIn('__smml_runtime_spine_ensure( "SurvivalPlayer.lua.file" )', patched)
        self.assertTrue(patched.endswith(original.decode("utf-8")))

    def test_survival_game_patch_injects_required_lifecycle_hooks(self) -> None:
        original = b"""function SurvivalGame.server_onCreate( self )\nend\nfunction SurvivalGame.server_onUnload( self )\nend\nfunction SurvivalGame.client_onCreate( self )\nend\nfunction SurvivalGame.client_onUpdate( self, dt )\nend\nfunction SurvivalGame.server_onFixedUpdate( self, timeStep )\nend\nfunction SurvivalGame.server_onPlayerJoined( self, player, newPlayer )\nend\nfunction SurvivalGame.server_onPlayerLeft( self, player )\nend\n"""
        patched = lab.patch_survival_game(original).decode("utf-8")
        for event in (
            "server.create",
            "server.unload",
            "client.create",
            "player.join",
            "player.left",
        ):
            self.assertEqual(patched.count(f'__smml_runtime_spine_lifecycle( "{event}"'), 1)

    def test_survival_game_patch_fails_closed_on_ambiguous_anchor(self) -> None:
        original = b"""function SurvivalGame.server_onCreate( self )\nend\nfunction SurvivalGame.server_onCreate( self )\nend\nfunction SurvivalGame.server_onUnload( self )\nend\nfunction SurvivalGame.client_onCreate( self )\nend\nfunction SurvivalGame.client_onUpdate( self, dt )\nend\nfunction SurvivalGame.server_onFixedUpdate( self, timeStep )\nend\nfunction SurvivalGame.server_onPlayerJoined( self, player, newPlayer )\nend\nfunction SurvivalGame.server_onPlayerLeft( self, player )\nend\n"""
        with self.assertRaises(RuntimeError):
            lab.patch_survival_game(original)

    def test_summary_requires_one_first_initialization_per_runtime(self) -> None:
        events = [
            {
                "event": "runtime.bootstrap",
                "runtimeId": "r1",
                "firstInitialization": "true",
                "source": "SurvivalPlayer.lua.file",
            },
            {
                "event": "runtime.bootstrap",
                "runtimeId": "r1",
                "firstInitialization": "false",
                "source": "SurvivalGame.lua.file",
            },
            {
                "event": "lifecycle.server.create",
                "runtimeId": "r1",
            },
        ]
        summary = lab.summarize(events, {"run_id": "R1", "role": "host"})
        self.assertTrue(summary["bootstrap_idempotent"])
        self.assertEqual(summary["runtime_count"], 1)
        self.assertEqual(summary["server_create_count"], 1)

    def test_contract_registry_summary_requires_expected_probe_sequence(self) -> None:
        events = [
            {
                "event": "runtime.bootstrap",
                "runtimeId": "r1",
                "firstInitialization": "true",
                "source": "SurvivalPlayer.lua.file",
            },
            {"event": "contract.dispatch", "runtimeId": "r1", "contract": "probe.echo@1", "contextSource": "local-probe", "result": "ok"},
            {"event": "contract.dispatch", "runtimeId": "r1", "contract": "probe.unknown@1", "contextSource": "local-probe", "result": "unknown_contract"},
            {"event": "contract.dispatch", "runtimeId": "r1", "contract": "probe.throw@1", "contextSource": "local-probe", "result": "handler_error"},
            {"event": "contract.dispatch", "runtimeId": "r1", "contract": "probe.echo@1", "contextSource": "local-probe", "result": "ok"},
            {"event": "contract.probe.complete", "runtimeId": "r1", "ok": "true"},
        ]
        summary = lab.summarize(events, {"run_id": "R2", "role": "host"})
        self.assertTrue(summary["contract_registry_passed"])
        self.assertTrue(summary["runtimes"]["r1"]["contract_probe_ok"])
        self.assertEqual(summary["runtimes"]["r1"]["contract_throw_isolated_count"], 1)


    def test_contract_registry_loader_uses_side_effect_factory(self) -> None:
        runtime_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "Runtime.lua").read_text("utf-8")
        registry_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "ContractRegistry.lua").read_text("utf-8")
        self.assertIn("__SMML_CONTRACT_REGISTRY_FACTORY = function", registry_source)
        self.assertIn("__SMML_CONTRACT_REGISTRY_FACTORY = nil", runtime_source)
        self.assertIn("local factory = __SMML_CONTRACT_REGISTRY_FACTORY", runtime_source)
        self.assertNotIn("local ok, factory = pcall( dofile", runtime_source)


    def test_survival_game_patch_injects_transport_adapter(self) -> None:
        original = b"""function SurvivalGame.server_onCreate( self )
end
function SurvivalGame.server_onUnload( self )
end
function SurvivalGame.client_onCreate( self )
end
function SurvivalGame.client_onUpdate( self, dt )
end
function SurvivalGame.server_onFixedUpdate( self, timeStep )
end
function SurvivalGame.server_onPlayerJoined( self, player, newPlayer )
end
function SurvivalGame.server_onPlayerLeft( self, player )
end
"""
        patched = lab.patch_survival_game(original).decode("utf-8")
        self.assertIn('__smml_runtime_spine_transportCall( "onServerCreate", self )', patched)
        self.assertIn('__smml_runtime_spine_transportCall( "onClientCreate", self )', patched)
        self.assertIn('__smml_runtime_spine_transportCall( "onClientUpdate", self, dt )', patched)
        self.assertIn("function SurvivalGame.sv_smmlRuntimeEnvelope", patched)
        self.assertIn("function SurvivalGame.cl_smmlRuntimeReply", patched)

    def test_transport_loader_uses_side_effect_factory(self) -> None:
        runtime_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "Runtime.lua").read_text("utf-8")
        transport_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "TransportService.lua").read_text("utf-8")
        self.assertIn("__SMML_TRANSPORT_SERVICE_FACTORY = function", transport_source)
        self.assertIn("__SMML_TRANSPORT_SERVICE_FACTORY = nil", runtime_source)
        self.assertIn("local factory = __SMML_TRANSPORT_SERVICE_FACTORY", runtime_source)
        self.assertNotIn("_G[", runtime_source)

    def test_transport_summary_requires_request_dispatch_and_reply(self) -> None:
        events = [
            {"event": "runtime.bootstrap", "runtimeId": "server", "firstInitialization": "true", "source": "SurvivalPlayer.lua.file"},
            {"event": "contract.dispatch", "runtimeId": "server", "contract": "probe.echo@1", "contextSource": "local-probe", "result": "ok"},
            {"event": "contract.dispatch", "runtimeId": "server", "contract": "probe.unknown@1", "contextSource": "local-probe", "result": "unknown_contract"},
            {"event": "contract.dispatch", "runtimeId": "server", "contract": "probe.throw@1", "contextSource": "local-probe", "result": "handler_error"},
            {"event": "contract.dispatch", "runtimeId": "server", "contract": "probe.echo@1", "contextSource": "local-probe", "result": "ok"},
            {"event": "contract.probe.complete", "runtimeId": "server", "ok": "true"},
        ]
        for request_id, expected in lab.TRANSPORT_EXPECTED.items():
            events.extend([
                {
                    "event": "transport.envelope.server",
                    "runtimeId": "server",
                    "requestId": request_id,
                    "contract": expected["contract"],
                    "senderIsHost": "false",
                    "result": "received",
                },
                {
                    "event": "contract.dispatch",
                    "runtimeId": "server",
                    "requestId": request_id,
                    "contract": expected["contract"],
                    "contextSource": "transport",
                    "result": expected["dispatch"],
                },
                {
                    "event": "transport.reply.server",
                    "runtimeId": "server",
                    "requestId": request_id,
                    "accepted": expected["accepted"],
                    "code": expected["code"],
                    "result": "sent",
                },
            ])
        summary = lab.summarize(events, {"run_id": "R3", "role": "host"})
        self.assertTrue(summary["contract_registry_passed"])
        self.assertTrue(summary["transport_server_passed"])
        self.assertTrue(summary["transport_passed"])
        self.assertTrue(all(item["ok"] for item in summary["transport_server_request_checks"].values()))

    def test_transport_client_summary_requires_all_replies(self) -> None:
        events = [
            {"event": "runtime.bootstrap", "runtimeId": "client", "firstInitialization": "true", "source": "SurvivalPlayer.lua.file"},
            {"event": "contract.dispatch", "runtimeId": "client", "contract": "probe.echo@1", "contextSource": "local-probe", "result": "ok"},
            {"event": "contract.dispatch", "runtimeId": "client", "contract": "probe.unknown@1", "contextSource": "local-probe", "result": "unknown_contract"},
            {"event": "contract.dispatch", "runtimeId": "client", "contract": "probe.throw@1", "contextSource": "local-probe", "result": "handler_error"},
            {"event": "contract.dispatch", "runtimeId": "client", "contract": "probe.echo@1", "contextSource": "local-probe", "result": "ok"},
            {"event": "contract.probe.complete", "runtimeId": "client", "ok": "true"},
        ]
        for request_id, expected in lab.TRANSPORT_EXPECTED.items():
            events.append({
                "event": "transport.reply.client",
                "runtimeId": "client",
                "requestId": request_id,
                "accepted": expected["accepted"],
                "code": expected["code"],
                "result": expected["result"],
            })
        events.append({"event": "transport.probe.complete", "runtimeId": "client", "ok": "true"})
        summary = lab.summarize(events, {"run_id": "R3", "role": "client"})
        self.assertTrue(summary["contract_registry_passed"])
        self.assertTrue(summary["transport_client_passed"])
        self.assertTrue(summary["transport_passed"])
        self.assertTrue(summary["runtimes"]["client"]["transport_client_ok"])

    def test_survival_game_patch_injects_storage_adapter(self) -> None:
        original = b"""function SurvivalGame.server_onCreate( self )
end
function SurvivalGame.server_onUnload( self )
end
function SurvivalGame.client_onCreate( self )
end
function SurvivalGame.client_onUpdate( self, dt )
end
function SurvivalGame.server_onFixedUpdate( self, timeStep )
end
function SurvivalGame.server_onPlayerJoined( self, player, newPlayer )
end
function SurvivalGame.server_onPlayerLeft( self, player )
end
"""
        patched = lab.patch_survival_game(original).decode("utf-8")
        self.assertIn('__smml_runtime_spine_storageCall( "onServerCreate", self )', patched)
        self.assertIn('__smml_runtime_spine_storageCall( "onServerFixedUpdate", self, timeStep )', patched)

    def test_storage_loader_uses_side_effect_factory(self) -> None:
        runtime_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "Runtime.lua").read_text("utf-8")
        storage_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "StorageService.lua").read_text("utf-8")
        self.assertIn("__SMML_STORAGE_SERVICE_FACTORY = function", storage_source)
        self.assertIn("__SMML_STORAGE_SERVICE_FACTORY = nil", runtime_source)
        self.assertIn("local factory = __SMML_STORAGE_SERVICE_FACTORY", runtime_source)

    def test_storage_summary_requires_three_session_sequence(self) -> None:
        events = [
            {"event": "runtime.bootstrap", "runtimeId": "s1", "firstInitialization": "true", "source": "SurvivalPlayer.lua.file"},
            {"event": "storage.load.absent", "runtimeId": "s1"},
            {"event": "storage.namespace.check", "runtimeId": "s1", "success": "true"},
            {"event": "storage.save.schema1", "runtimeId": "s1"},
            {"event": "storage.probe.complete", "runtimeId": "s1", "phase": "schema1_saved", "ok": "true"},
            {"event": "runtime.bootstrap", "runtimeId": "s2", "firstInitialization": "true", "source": "SurvivalPlayer.lua.file"},
            {"event": "storage.namespace.check", "runtimeId": "s2", "success": "true"},
            {"event": "storage.load.schema1", "runtimeId": "s2"},
            {"event": "storage.migration.1to2", "runtimeId": "s2"},
            {"event": "storage.save.schema2", "runtimeId": "s2"},
            {"event": "storage.probe.complete", "runtimeId": "s2", "phase": "schema2_migrated", "ok": "true"},
            {"event": "runtime.bootstrap", "runtimeId": "s3", "firstInitialization": "true", "source": "SurvivalPlayer.lua.file"},
            {"event": "storage.namespace.check", "runtimeId": "s3", "success": "true"},
            {"event": "storage.load.schema2", "runtimeId": "s3"},
            {"event": "storage.probe.complete", "runtimeId": "s3", "phase": "schema2_stable", "ok": "true"},
        ]
        summary = lab.summarize(events, {"run_id": "R4", "role": "host"})
        self.assertTrue(summary["storage_server_passed"])
        self.assertTrue(summary["storage_passed"])
        self.assertEqual(summary["storage_probe_phases"], ["schema1_saved", "schema2_migrated", "schema2_stable"])

    def test_storage_client_summary_requires_no_backend_activity(self) -> None:
        events = [
            {"event": "runtime.bootstrap", "runtimeId": "c1", "firstInitialization": "true", "source": "SurvivalPlayer.lua.file"},
            {"event": "storage.service.loaded", "runtimeId": "c1", "result": "ok"},
        ]
        summary = lab.summarize(events, {"run_id": "R4", "role": "client"})
        self.assertTrue(summary["storage_client_quiet"])
        self.assertTrue(summary["storage_passed"])


    def test_carry_adapter_loader_uses_side_effect_factory(self) -> None:
        runtime_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "Runtime.lua").read_text("utf-8")
        carry_source = (ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "CarryAdapter.lua").read_text("utf-8")
        self.assertIn("__SMML_CARRY_ADAPTER_FACTORY = function", carry_source)
        self.assertIn("__SMML_CARRY_ADAPTER_FACTORY = nil", runtime_source)
        self.assertIn("local factory = __SMML_CARRY_ADAPTER_FACTORY", runtime_source)
        self.assertNotIn("sendToServer", carry_source)

    def test_carry_tool_patch_injects_final_empty_hook_and_vanilla_relay_observer(self) -> None:
        original = b"""function CarryTool.cl_tryInsert( self, character, primaryState, playerCarry, carryUuid, playerCarryColor )
	local success, result = sm.localPlayer.getRaycast( 7.5 )
	return false
end

function CarryTool.cl_tryDrop( self, primaryState, secondaryState, playerCarry, carryUuid, characterShape, playerCarryColor )
end

function CarryTool.sv_n_sendItem( self, params, player )
	params.player = player
	sm.event.sendToInteractable( params.targetShape.interactable, "sv_e_receiveItem", params )
end
"""
        patched = lab.patch_carry_tool(original).decode("utf-8")
        self.assertIn("SMML_RUNTIME_SPINE_BEGIN:bootstrap:CarryTool.lua", patched)
        self.assertIn("SMML_RUNTIME_SPINE_BEGIN:carry.resolveInsertTarget@1", patched)
        self.assertIn("__SMML_RUNTIME.carry.resolveInsertTarget", patched)
        self.assertIn("__SMML_RUNTIME.carry.onVanillaServerRelay", patched)
        hook_pos = patched.index("SMML_RUNTIME_SPINE_BEGIN:carry.resolveInsertTarget@1")
        final_false_pos = patched.index("\n\treturn false\nend\n\nfunction CarryTool.cl_tryDrop")
        self.assertLess(hook_pos, final_false_pos)

    def test_carry_summary_requires_empty_client_hook_and_vanilla_server_relay(self) -> None:
        client_events = [
            {"event": "runtime.bootstrap", "runtimeId": "c1", "firstInitialization": "true", "source": "CarryTool.lua.file"},
            {"event": "carry.resolve.empty", "runtimeId": "c1"},
        ]
        client_summary = lab.summarize(client_events, {"run_id": "R5", "role": "client"})
        self.assertTrue(client_summary["carry_client_passed"])
        self.assertTrue(client_summary["carry_passed"])

        host_events = [
            {"event": "runtime.bootstrap", "runtimeId": "s1", "firstInitialization": "true", "source": "CarryTool.lua.file"},
            {"event": "carry.vanilla.rpc.server", "runtimeId": "s1"},
        ]
        host_summary = lab.summarize(host_events, {"run_id": "R5", "role": "host"})
        self.assertTrue(host_summary["carry_server_passed"])
        self.assertTrue(host_summary["carry_passed"])

    def test_normal_smml_event_is_not_reported_as_lua_diagnostic(self) -> None:
        line = "[Lua] ERROR: [SMML-RUNTIME] EVT|schema=1|event=contract.dispatch|runId=R2"
        event = lab.parse_event_line(line)
        self.assertIsNotNone(event)
        self.assertFalse(lab.is_diagnostic_line(line, event))
        self.assertTrue(lab.is_diagnostic_line("[Lua] ERROR: unrelated failure", None))
        self.assertTrue(lab.is_diagnostic_line("[SMML-RUNTIME] FALLBACK|stage=test", None))


if __name__ == "__main__":
    unittest.main()
