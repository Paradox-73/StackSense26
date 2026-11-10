"""Hosts that build an app from source with official buildpacks list those languages as adjacent skills, so a
team's server language counts the same on each of them (DigitalOcean App Platform: Go, Node.js, PHP, Python,
Ruby; Cloud Run: Go, Node.js, Python, Java, Ruby, PHP, .NET)."""
from engine.kb import load_kb
from engine.scoring import skill_fit


def _host(hid):
    return next(i for i in load_kb()["hosting"] if i["id"] == hid)


def test_buildpack_languages_are_adjacent_skills():
    assert {"python", "node", "go", "ruby", "php"} <= set(_host("digitalocean")["related_skills"])
    assert {"python", "node", "go", "ruby", "php", "java", "dotnet"} <= set(_host("gcp_cloud_run")["related_skills"])
    assert any("buildpacks/python" in s for s in _host("digitalocean")["sources"])
    assert any("buildpacks/overview" in s for s in _host("gcp_cloud_run")["sources"])


def test_python_team_fits_both_buildpack_hosts_alike():
    skills = {"python", "django", "postgres"}
    assert skill_fit(_host("digitalocean"), skills) == skill_fit(_host("gcp_cloud_run"), skills) == 3.5
