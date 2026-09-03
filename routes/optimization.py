"""POST endpoints that recompute the optimization model against a caller-
supplied set of assumption overrides (used by Cost Optimization, the
What-If Simulator, and the appendix methodology/output pages).
"""
from flask import Blueprint, jsonify, request

from services import optimization_service

optimization_bp = Blueprint("optimization", __name__)


def _overrides_from_request() -> dict:
    return request.get_json(silent=True) or {}


@optimization_bp.route("/optimize", methods=["POST"])
def optimize():
    return jsonify(optimization_service.optimize(_overrides_from_request()))


@optimization_bp.route("/simulate", methods=["POST"])
def simulate():
    return jsonify(optimization_service.simulate(_overrides_from_request()))
