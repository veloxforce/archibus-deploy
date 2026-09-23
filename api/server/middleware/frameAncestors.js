/**
 * Restrict who may frame this app. ALLOWED_FRAME_ANCESTORS is a space-separated list of
 * origins (e.g. "https://spro-sp.bruceplatform.com"); when set, every response carries
 * `Content-Security-Policy: frame-ancestors <list>`. Unset = no header (upstream behavior).
 */
const buildFrameAncestors = (raw) => {
  const sources = (raw || '').split(/\s+/).filter(Boolean);
  return sources.length ? `frame-ancestors ${sources.join(' ')}` : null;
};

const frameAncestors = (req, res, next) => {
  const policy = buildFrameAncestors(process.env.ALLOWED_FRAME_ANCESTORS);
  if (policy) {
    res.setHeader('Content-Security-Policy', policy);
  }
  next();
};

module.exports = frameAncestors;
module.exports.buildFrameAncestors = buildFrameAncestors;
