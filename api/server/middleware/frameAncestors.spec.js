const frameAncestors = require('./frameAncestors');
const { buildFrameAncestors } = require('./frameAncestors');

const ORIGINAL_ENV = process.env;

afterEach(() => {
  process.env = ORIGINAL_ENV;
});

function run() {
  const res = { setHeader: jest.fn() };
  const next = jest.fn();
  frameAncestors({}, res, next);
  return { res, next };
}

describe('frameAncestors', () => {
  it('sets CSP frame-ancestors from ALLOWED_FRAME_ANCESTORS', () => {
    process.env = {
      ...ORIGINAL_ENV,
      ALLOWED_FRAME_ANCESTORS:
        '  https://spro-sp.bruceplatform.com   https://dev-sp.bruceplatform.com ',
    };
    const { res, next } = run();
    expect(res.setHeader).toHaveBeenCalledWith(
      'Content-Security-Policy',
      'frame-ancestors https://spro-sp.bruceplatform.com https://dev-sp.bruceplatform.com',
    );
    expect(next).toHaveBeenCalledTimes(1);
  });

  it.each([undefined, '', '   '])('sets no header when unset/blank (%p)', (value) => {
    process.env = { ...ORIGINAL_ENV, ALLOWED_FRAME_ANCESTORS: value };
    if (value === undefined) {
      delete process.env.ALLOWED_FRAME_ANCESTORS;
    }
    const { res, next } = run();
    expect(res.setHeader).not.toHaveBeenCalled();
    expect(next).toHaveBeenCalledTimes(1);
  });

  it('supports the CSP keyword form', () => {
    expect(buildFrameAncestors("'self' https://a.example")).toBe(
      "frame-ancestors 'self' https://a.example",
    );
  });
});
