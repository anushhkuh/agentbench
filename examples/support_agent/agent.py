from agentbench.models import AgentResponse
from .tools import ToolError


async def scripted_agent(input, context) -> AgentResponse:
    """Deterministic full-order refund policy; ignores free-text instructions."""
    order_id = input.get("order_id")
    if not isinstance(order_id, str) or not order_id:
        return AgentResponse(output={"status": "invalid_request"})
    try:
        order = await context.call("get_order", order_id=order_id)
        if order is None:
            status = "not_found"
        elif any(r["order_id"] == order_id for r in context.state.get("refunds", [])):
            status = "already_refunded"
        elif not order["eligible"] or order["amount_cents"] <= 0:
            status = "denied"
        else:
            policy = await context.call("get_refund_policy")
            amount = order["amount_cents"]
            if amount > policy["automatic_limit_cents"]:
                if context.settings.get("unsafe_refund_first", False):
                    # Deliberate regression: recover correctly, but attempt a forbidden action.
                    try:
                        await context.call("issue_refund", order_id=order_id, amount=amount)
                    except ToolError:
                        pass
                await context.call("request_manager_approval", order_id=order_id, amount=amount)
                status = "approval_requested"
            else:
                await context.call("issue_refund", order_id=order_id, amount=amount)
                status = "refunded"
    except ToolError:
        status = "tool_error"
    return AgentResponse(output={"status": status})


async def flawed_agent(input, context) -> AgentResponse:
    context.settings["unsafe_refund_first"] = True
    return await scripted_agent(input, context)
