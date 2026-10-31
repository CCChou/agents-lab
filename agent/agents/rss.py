from agent.adapters.miniflux import MinifluxQueryTool
from agent.domain.agent_spec import AgentSpec

SYSTEM_PROMPT = (
    "你是使用者的 RSS 閱讀助理。需要文章資訊時，使用工具查詢 Miniflux，不要憑空捏造文章。"
    "回答時使用使用者的語言，並在提到文章時附上標題和網址。"
)


def build_rss_spec(system_prompt: str | None = None) -> AgentSpec:
    return AgentSpec(
        name="rss",
        system_prompt=system_prompt or SYSTEM_PROMPT,
        tools=(MinifluxQueryTool.name,),
    )
