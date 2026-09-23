const mockFindUser = jest.fn();
const mockLogger = { info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() };

jest.mock('@librechat/data-schemas', () => ({ logger: mockLogger }));
jest.mock('@librechat/api', () => ({
  isEnabled: (value) => typeof value === 'string' && value.toLowerCase().trim() === 'true',
}));
jest.mock('~/models', () => ({ findUser: (...args) => mockFindUser(...args) }));

const requireBruceToken = require('./requireBruceToken');

const SECRET = 'bruce-user-token-must-never-be-logged';
const SERVICE_USER = { _id: { toString: () => 'u1' }, email: 'svc@example.com' };

function buildRes() {
  return {
    status: jest.fn().mockReturnThis(),
    json: jest.fn().mockReturnThis(),
    send: jest.fn().mockReturnThis(),
  };
}

const ORIGINAL_ENV = process.env;
const ORIGINAL_FETCH = global.fetch;

beforeEach(() => {
  jest.clearAllMocks();
  process.env = {
    ...ORIGINAL_ENV,
    AUTO_LOGIN_ENABLED: 'true',
    AUTO_LOGIN_EMAIL: 'svc@example.com',
    BRUCE_TOKEN_VALIDATE_URL: 'http://validator.test/auth/validate',
  };
  global.fetch = jest.fn();
  mockFindUser.mockResolvedValue(SERVICE_USER);
});

afterAll(() => {
  process.env = ORIGINAL_ENV;
  global.fetch = ORIGINAL_FETCH;
});

async function run(body) {
  const req = { body, ip: '127.0.0.1' };
  const res = buildRes();
  const next = jest.fn();
  await requireBruceToken(req, res, next);
  return { req, res, next };
}

describe('requireBruceToken', () => {
  it('sets req.user to the service account when the validator answers 2xx', async () => {
    global.fetch.mockResolvedValue({ ok: true, status: 204 });
    const { req, res, next } = await run({ userToken: SECRET });

    expect(next).toHaveBeenCalledTimes(1);
    expect(res.status).not.toHaveBeenCalled();
    expect(req.user).toBe(SERVICE_USER);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://validator.test/auth/validate',
      expect.objectContaining({ method: 'GET', headers: { 'X-Rain-User-Token': SECRET } }),
    );
    expect(mockFindUser).toHaveBeenCalledWith(
      { email: 'svc@example.com' },
      '-password -totpSecret -backupCodes',
    );
  });

  it.each([[undefined], [{}], [{ userToken: '' }], [{ userToken: '   ' }], [{ userToken: 42 }]])(
    'rejects a missing/blank token (%p) with 401 without calling the validator',
    async (body) => {
      const { req, res, next } = await run(body);
      expect(res.status).toHaveBeenCalledWith(401);
      expect(next).not.toHaveBeenCalled();
      expect(req.user).toBeUndefined();
      expect(global.fetch).not.toHaveBeenCalled();
    },
  );

  it.each([401, 400, 500, 502])(
    'rejects with 401 when the validator answers %i',
    async (status) => {
      global.fetch.mockResolvedValue({ ok: false, status });
      const { req, res, next } = await run({ userToken: 'x' });
      expect(res.status).toHaveBeenCalledWith(401);
      expect(next).not.toHaveBeenCalled();
      expect(req.user).toBeUndefined();
      expect(mockFindUser).not.toHaveBeenCalled();
    },
  );

  it('fails closed (401) when the validator is unreachable', async () => {
    global.fetch.mockRejectedValue(Object.assign(new Error('ECONNREFUSED'), { name: 'TypeError' }));
    const { res, next } = await run({ userToken: 'x' });
    expect(res.status).toHaveBeenCalledWith(401);
    expect(next).not.toHaveBeenCalled();
  });

  it('uses the in-network default validator URL when unset', async () => {
    delete process.env.BRUCE_TOKEN_VALIDATE_URL;
    global.fetch.mockResolvedValue({ ok: true, status: 204 });
    await run({ userToken: 'x' });
    expect(global.fetch.mock.calls[0][0]).toBe('http://archibus_fastmcp:8000/auth/validate');
  });

  it('is closed (404) unless AUTO_LOGIN_ENABLED=true', async () => {
    process.env.AUTO_LOGIN_ENABLED = 'false';
    const { res, next } = await run({ userToken: SECRET });
    expect(res.status).toHaveBeenCalledWith(404);
    expect(next).not.toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('answers 500 (no session) when the service account does not exist', async () => {
    global.fetch.mockResolvedValue({ ok: true, status: 204 });
    mockFindUser.mockResolvedValue(null);
    const { res, next } = await run({ userToken: 'x' });
    expect(res.status).toHaveBeenCalledWith(500);
    expect(next).not.toHaveBeenCalled();
  });

  it('never logs the user token', async () => {
    for (const outcome of [
      () => global.fetch.mockResolvedValue({ ok: true, status: 204 }),
      () => global.fetch.mockResolvedValue({ ok: false, status: 401 }),
      () => global.fetch.mockRejectedValue(new Error('down')),
    ]) {
      outcome();
      await run({ userToken: SECRET });
    }
    const logged = JSON.stringify(
      Object.values(mockLogger).flatMap((fn) => fn.mock.calls),
      (_k, v) => (v instanceof Error ? v.message : v),
    );
    expect(logged).not.toContain(SECRET);
  });
});
