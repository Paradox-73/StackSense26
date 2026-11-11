/* The 3-way theme switch (system, light, dark) shared by every page. The inline script in each page's <head> applies
   the saved theme before first paint; this binds the radio buttons and saves the choice. */
"use strict";
(function () {
  let t = "auto";
  try { t = new URLSearchParams(location.search).get("theme") || localStorage.getItem("ss-theme") || "auto"; } catch (e) { /* storage blocked */ }
  if (!["light", "dark"].includes(t)) t = "auto";
  document.querySelectorAll('.theme input[name="theme"]').forEach((r) => {
    r.checked = r.value === t;
    r.onchange = () => {
      if (r.value === "auto") document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", r.value);
      try { localStorage.setItem("ss-theme", r.value); } catch (e) { /* storage blocked */ }
    };
  });
})();
