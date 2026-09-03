/* localStorage-backed store for user-editable assumption parameters, shared
 * across the Cost Optimization / Scenario / Sensitivity / Assumptions
 * screens so an edit on one is reflected everywhere. The What-If Simulator
 * deliberately does NOT write through here on every slider drag -- only an
 * explicit "Apply as new baseline" action does -- so casual exploration
 * doesn't silently change other screens.
 */
(function (global) {
  const STORAGE_KEY = "sscm_assumptions";
  let cache = null;
  let defaultsCache = null;

  function readStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function writeStorage(obj) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
    } catch (e) {}
  }

  async function fetchDefaults() {
    if (defaultsCache) return defaultsCache;
    const res = await fetch("/api/assumptions/defaults");
    const data = await res.json();
    defaultsCache = data.parameters;
    return defaultsCache;
  }

  async function get() {
    if (cache) return cache;
    const defaults = await fetchDefaults();
    const overrides = readStorage();
    cache = {};
    defaults.forEach((p) => {
      cache[p.key] = overrides.hasOwnProperty(p.key) ? overrides[p.key] : p.value;
    });
    return cache;
  }

  async function set(partial) {
    const current = await get();
    Object.assign(current, partial);
    writeStorage(current);
    cache = current;
    return current;
  }

  async function reset() {
    writeStorage({});
    cache = null;
    return get();
  }

  async function defaultsCatalog() {
    return fetchDefaults();
  }

  async function toQueryString() {
    const current = await get();
    return new URLSearchParams(current).toString();
  }

  global.AssumptionsStore = { get, set, reset, defaultsCatalog, toQueryString };
})(window);
