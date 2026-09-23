/**
 * Bruce token door — the auth step of POST /api/auth/bruce { userToken }.
 *
 * The Bruce iframe opens the chat with ?userToken=...; the client posts that token here.
 * We ask archibus_fastmcp (GET BRUCE_TOKEN_VALIDATE_URL, header X-Rain-User-Token), which
 * checks it against Bruce itself. Only on a 2xx is req.user set — to the shared service
 * account named by AUTO_LOGIN_EMAIL — so the route can hand over to the stock
 * setBalanceConfig + loginController exactly as local login does. Anything else is a 401
 * and no session. No password is involved and none is ever sent to the browser.
 *
 * The user token is never logged.
 */
const { logger } = require('@librechat/data-schemas');
const { isEnabled } = require('@librechat/api');
const { findUser } = require('~/models');

const DEFAULT_VALIDATE_URL = 'http://archibus_fastmcp:8000/auth/validate';
const VALIDATE_TIMEOUT_MS = 15000;
const TOKEN_HEADER = 'X-Rain-User-Token';
const MAX_TOKEN_LENGTH = 8192;

const unauthorized = (res) => res.status(401).json({ message: 'Invalid or expired Bruce token' });

/** @returns {Promise<boolean>} true only when the validator answered 2xx */
async function isBruceTokenValid(userToken) {
  const url = process.env.BRUCE_TOKEN_VALIDATE_URL || DEFAULT_VALIDATE_URL;
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: { [TOKEN_HEADER]: userToken },
      signal: AbortSignal.timeout(VALIDATE_TIMEOUT_MS),
    });
    if (!response.ok) {
      logger.warn(`[requireBruceToken] Bruce token rejected (validator ${response.status})`);
    }
    return response.ok;
  } catch (err) {
    logger.error(`[requireBruceToken] token validator unreachable: ${err?.name ?? 'Error'}`);
    return false;
  }
}

const requireBruceToken = async (req, res, next) => {
  try {
    if (!isEnabled(process.env.AUTO_LOGIN_ENABLED)) {
      return res.status(404).json({ message: 'Not found' });
    }

    const userToken = req.body?.userToken;
    if (
      typeof userToken !== 'string' ||
      userToken.trim() === '' ||
      userToken.length > MAX_TOKEN_LENGTH
    ) {
      return unauthorized(res);
    }

    if (!(await isBruceTokenValid(userToken))) {
      return unauthorized(res);
    }

    const email = process.env.AUTO_LOGIN_EMAIL;
    if (!email) {
      logger.error('[requireBruceToken] AUTO_LOGIN_EMAIL is not set');
      return res.status(500).json({ message: 'Something went wrong' });
    }

    const user = await findUser({ email: email.trim() }, '-password -totpSecret -backupCodes');
    if (!user) {
      logger.error('[requireBruceToken] AUTO_LOGIN_EMAIL names no user in this deployment');
      return res.status(500).json({ message: 'Something went wrong' });
    }

    logger.info(`[requireBruceToken] Bruce token accepted [Request-IP: ${req.ip}]`);
    req.user = user;
    return next();
  } catch (err) {
    logger.error('[requireBruceToken]', err);
    return res.status(500).json({ message: 'Something went wrong' });
  }
};

module.exports = requireBruceToken;
module.exports.isBruceTokenValid = isBruceTokenValid;
