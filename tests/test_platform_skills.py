"""A managed Kubernetes cluster needs Kubernetes skills to operate: listing the cloud that sells it (AWS for EKS,
GCP for GKE) does not remove the "requires platform skills" penalty; listing Kubernetes does."""
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import score_layer, build_weights

BASE = {"app_type": "saas", "platforms": ["web"], "dau": 50000, "team_size": 10, "timeline_weeks": 16,
        "budget_monthly": 8000, "currency": "USD", "deployment": "cloud", "cloud_preference": "aws"}
PENALTY = "Requires platform/DevOps skills your team did not list"


def _penalised(skills, host="aws_eks"):
    p, a, w = normalize(dict(BASE, team_skills=skills))
    d = derive(p, a, w)
    item = next(i for i in load_kb()["hosting"] if i["id"] == host)
    cands, _ = score_layer("hosting", [item], p, d, build_weights(p, d), force=(host,))
    return any(x["reason"] == PENALTY for x in cands[0]["adjustments"])


def test_cloud_account_is_not_kubernetes_skill():
    assert _penalised(["aws", "docker", "node"])
    assert _penalised(["gcp", "docker"], host="gcp_gke")


def test_kubernetes_skill_removes_the_penalty():
    assert not _penalised(["aws", "kubernetes"])
    assert not _penalised(["kubernetes"], host="gcp_gke")
