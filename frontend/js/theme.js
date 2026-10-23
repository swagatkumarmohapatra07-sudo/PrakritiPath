/* Theme bootstrap — loaded synchronously in <head> to avoid a flash. */
(function () {
  try {
    var stored = localStorage.getItem("biotrace_theme");
    var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    var theme = stored || (prefersDark ? "dark" : "light");
    document.documentElement.dataset.theme = theme;
  } catch (err) {
    document.documentElement.dataset.theme = "light";
  }
})();
