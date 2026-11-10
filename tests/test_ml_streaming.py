"""An ML product streams model output (tokens over server-sent events or WebSockets), so it weights realtime
fit a little even when the realtime answer is left at its default; among Python backends this favours the
async-first FastAPI over Django when the rest of the stack is equal."""
from engine import recommend
from engine.profile import derive, normalize
from engine.scoring import build_weights

ML = {"app_type": "ml_product", "platforms": ["web"], "dau": 5000, "data_shapes": ["vector", "relational"],
      "team_size": 5, "team_skills": ["python", "react", "postgres"], "timeline_weeks": 12,
      "budget_monthly": 5000, "currency": "USD", "deployment": "cloud", "realtime": "some"}


def _realtime_weight(raw):
    p, a, w = normalize(raw)
    d = derive(p, a, w)
    return build_weights(p, d).total("realtime")


def test_ml_product_weights_streaming():
    assert _realtime_weight(ML) > _realtime_weight(dict(ML, app_type="saas"))


def test_ml_product_python_backend_is_fastapi():
    assert recommend(ML)["stack"]["backend"]["pick"]["id"] == "fastapi"
