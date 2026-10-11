from app.agents.graphs.mini import CompiledGraph
from app.agents.plugin import AgentPlugin, AgentRegistry, registry


def _plugin(agent_id: str, intents: list[str]) -> AgentPlugin:
    async def run(state):
        return state

    return AgentPlugin(
        agent_id=agent_id,
        display_name=agent_id,
        description="",
        version="0.0.1",
        owner_team="t",
        intents=intents,
        scopes=[],
        graph_factory=lambda: CompiledGraph(run),
    )


def test_bundled_agents_register_their_intents():
    table = registry.routing_table()
    assert table["create_booking"] == "booking"
    assert table["track_shipment"] == "tracking"


def test_later_registration_wins_a_contested_intent():
    reg = AgentRegistry()
    reg.register(_plugin("a", ["x"]))
    reg.register(_plugin("b", ["x", "y"]))
    assert reg.routing_table() == {"x": "b", "y": "b"}


def test_graph_factory_is_called_once():
    calls = []
    plugin = _plugin("a", [])
    original = plugin.graph_factory
    plugin.graph_factory = lambda: calls.append(1) or original()
    assert plugin.graph is plugin.graph
    assert len(calls) == 1
