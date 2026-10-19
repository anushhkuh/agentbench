"""Mock-only support tools. Amounts are integer cents throughout."""
from copy import deepcopy


class ToolError(Exception):
    pass


def support_tools(state):
    def check_failure(name):
        if name in state.get("fail_tools", []):
            raise ToolError(f"{name} unavailable")

    def order_for(order_id):
        order = state.get("orders", {}).get(order_id)
        if order is None:
            raise ToolError("order not found")
        return order

    def validate(order_id, amount):
        order = order_for(order_id)
        if not order["eligible"]:
            raise ToolError("order is ineligible")
        if type(amount) is not int or amount <= 0 or amount != order["amount_cents"]:
            raise ToolError("amount must equal the positive order total")
        return order

    async def get_order(order_id):
        check_failure("get_order")
        return deepcopy(state.get("orders", {}).get(order_id))

    async def get_refund_policy():
        check_failure("get_refund_policy")
        return deepcopy(state["policy"])

    async def issue_refund(order_id, amount):
        check_failure("issue_refund")
        validate(order_id, amount)
        if amount > state["policy"]["automatic_limit_cents"]:
            raise ToolError("manager approval required")
        refunds = state.setdefault("refunds", [])
        existing = next((r for r in refunds if r["order_id"] == order_id), None)
        if existing:
            return deepcopy(existing)
        record = {"order_id": order_id, "amount_cents": amount}
        refunds.append(record)
        return deepcopy(record)

    async def request_manager_approval(order_id, amount):
        check_failure("request_manager_approval")
        validate(order_id, amount)
        if any(r["order_id"] == order_id for r in state.get("refunds", [])):
            raise ToolError("order already refunded")
        approvals = state.setdefault("approvals", [])
        record = {"order_id": order_id, "amount_cents": amount}
        if record not in approvals:
            approvals.append(record)
        return deepcopy(record)

    return {fn.__name__: fn for fn in (
        get_order, get_refund_policy, issue_refund, request_manager_approval
    )}
