/* Share a project as a link or a file. No dependencies, so it also runs under Node for the tests.
   A link carries only the answers the user gave (plus the ones marked "Not sure"), as URL-safe base64 of JSON:
   opening it on another machine gives the same answers, and the engine is deterministic, so the same stack. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Share = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const PREFIX = "v1.";
  const MAX_CHARS = 20000;
  const FILE_MARK = "stacksense_answers";

  function toB64(text) {
    const bytes = new TextEncoder().encode(text);
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function fromB64(s) {
    const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
    const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }

  /** answers: {key: value} the user gave; unknown: keys marked "Not sure". Returns the text after "#a=". */
  function encode(answers, unknown) {
    return PREFIX + toB64(JSON.stringify({ a: answers || {}, u: [...(unknown || [])] }));
  }

  /** Inverse of encode. Returns {answers, unknown} or null when the text is not a valid link payload. */
  function decode(text) {
    try {
      if (typeof text !== "string" || !text.startsWith(PREFIX) || text.length > MAX_CHARS) return null;
      const o = JSON.parse(fromB64(text.slice(PREFIX.length)));
      if (!o || typeof o.a !== "object" || o.a === null || Array.isArray(o.a)) return null;
      return { answers: o.a, unknown: Array.isArray(o.u) ? o.u.filter((k) => typeof k === "string") : [] };
    } catch (e) {
      return null;
    }
  }

  /** The text of the downloadable answers file. */
  function toFile(answers, unknown) {
    return JSON.stringify({ [FILE_MARK]: 1, answers: answers || {}, not_sure: [...(unknown || [])] }, null, 2);
  }

  /** Read an answers file. Accepts the file above, a scenario ({"input": {...}}) or a bare answers object.
   *  isKey(k) says whether k is a known question; others are returned in `ignored`. Returns null if unreadable. */
  function fromFile(text, isKey) {
    let o;
    try { o = JSON.parse(text); } catch (e) { return null; }
    if (!o || typeof o !== "object" || Array.isArray(o)) return null;
    let src = o, unknown = [];
    if (o[FILE_MARK] && o.answers && typeof o.answers === "object") { src = o.answers; unknown = Array.isArray(o.not_sure) ? o.not_sure : []; }
    else if (o.input && typeof o.input === "object" && !Array.isArray(o.input)) src = o.input;
    const answers = {}, ignored = [];
    for (const k of Object.keys(src)) (isKey(k) ? (answers[k] = src[k]) : ignored.push(k));
    return { answers, unknown: unknown.filter((k) => typeof k === "string" && isKey(k)), ignored };
  }

  return { encode, decode, toFile, fromFile };
});
