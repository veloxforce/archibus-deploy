import { useEffect, useRef, useState } from 'react';
import { ErrorTypes } from 'librechat-data-provider';
import { OpenIDIcon, useToastContext } from '@librechat/client';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import type { TLoginLayoutContext } from '~/common';
import { ErrorMessage } from '~/components/Auth/ErrorMessage';
import SocialButton from '~/components/Auth/SocialButton';
import { useAuthContext } from '~/hooks/AuthContext';
import { getLoginError } from '~/utils';
import { useLocalize } from '~/hooks';
import LoginForm from './LoginForm';

function Login() {
  const localize = useLocalize();
  const { showToast } = useToastContext();
  const { error, setError, login, bruceLogin } = useAuthContext();
  const { startupConfig } = useOutletContext<TLoginLayoutContext>();

  const [searchParams, setSearchParams] = useSearchParams();
  // Determine if auto-redirect should be disabled based on the URL parameter
  const disableAutoRedirect = searchParams.get('redirect') === 'false';

  // Persist the disable flag locally so that once detected, auto-redirect stays disabled.
  const [isAutoRedirectDisabled, setIsAutoRedirectDisabled] = useState(disableAutoRedirect);

  useEffect(() => {
    const oauthError = searchParams?.get('error');
    if (oauthError && oauthError === ErrorTypes.AUTH_FAILED) {
      showToast({
        message: localize('com_auth_error_oauth_failed'),
        status: 'error',
      });
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('error');
      setSearchParams(newParams, { replace: true });
    }
  }, [searchParams, setSearchParams, showToast, localize]);

  // Once the disable flag is detected, update local state and remove the parameter from the URL.
  useEffect(() => {
    if (disableAutoRedirect) {
      setIsAutoRedirectDisabled(true);
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('redirect');
      setSearchParams(newParams, { replace: true });
    }
  }, [disableAutoRedirect, searchParams, setSearchParams]);

  // Determine whether we should auto-redirect to OpenID.
  const shouldAutoRedirect =
    startupConfig?.openidLoginEnabled &&
    startupConfig?.openidAutoRedirect &&
    startupConfig?.serverDomain &&
    !isAutoRedirectDisabled;

  useEffect(() => {
    if (shouldAutoRedirect) {
      console.log('Auto-redirecting to OpenID provider...');
      window.location.href = `${startupConfig.serverDomain}/oauth/openid`;
    }
  }, [shouldAutoRedirect, startupConfig]);

  // RAIN TOKEN CAPTURE: Must happen BEFORE auto-login redirect.
  // Tokens are delivered via iframe URL params from Rain (Bruce BEM's auth system).
  // We capture them immediately on Login page load and store in sessionStorage,
  // so they persist through the auto-login redirect to the chat interface.
  useEffect(() => {
    const userToken = searchParams.get('userToken');
    const refreshToken = searchParams.get('refreshToken');

    if (userToken) {
      sessionStorage.setItem('rainUserToken', userToken);
      console.log('Rain userToken captured and stored');
    }
    if (refreshToken) {
      sessionStorage.setItem('rainRefreshToken', refreshToken);
      console.log('Rain refreshToken captured and stored');
    }

    // Clean tokens from URL (optional - keeps URL tidy)
    if (userToken || refreshToken) {
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('userToken');
      newParams.delete('refreshToken');
      setSearchParams(newParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // BRUCE TOKEN DOOR: the iframe's Bruce user token (captured above and in App.jsx) is the
  // only key. POST /api/auth/bruce validates it against Bruce and opens the session; success
  // and failure run through AuthContext's own login handlers. No token → no auto-login: the
  // normal login form below is all a visitor without Bruce gets.
  const bruceLoginAttempted = useRef(false);
  useEffect(() => {
    if (!startupConfig?.autoLoginEnabled || bruceLoginAttempted.current) {
      return;
    }
    const userToken = searchParams.get('userToken') ?? sessionStorage.getItem('rainUserToken');
    if (!userToken) {
      return;
    }
    bruceLoginAttempted.current = true;
    bruceLogin(userToken);
  }, [startupConfig, bruceLogin, searchParams]);

  // Render fallback UI if auto-redirect is active.
  if (shouldAutoRedirect) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4">
        <p className="text-lg font-semibold">
          {localize('com_ui_redirecting_to_provider', { 0: startupConfig.openidLabel })}
        </p>
        <div className="mt-4">
          <SocialButton
            key="openid"
            enabled={startupConfig.openidLoginEnabled}
            serverDomain={startupConfig.serverDomain}
            oauthPath="openid"
            Icon={() =>
              startupConfig.openidImageUrl ? (
                <img src={startupConfig.openidImageUrl} alt="OpenID Logo" className="h-5 w-5" />
              ) : (
                <OpenIDIcon />
              )
            }
            label={startupConfig.openidLabel}
            id="openid"
          />
        </div>
      </div>
    );
  }

  return (
    <>
      {error != null && <ErrorMessage>{localize(getLoginError(error))}</ErrorMessage>}
      {startupConfig?.emailLoginEnabled === true && (
        <LoginForm
          onSubmit={login}
          startupConfig={startupConfig}
          error={error}
          setError={setError}
        />
      )}
      {startupConfig?.registrationEnabled === true && (
        <p className="my-4 text-center text-sm font-light text-gray-700 dark:text-white">
          {' '}
          {localize('com_auth_no_account')}{' '}
          <a
            href="/register"
            className="inline-flex p-1 text-sm font-medium text-green-600 transition-colors hover:text-green-700 dark:text-green-400 dark:hover:text-green-300"
          >
            {localize('com_auth_sign_up')}
          </a>
        </p>
      )}
    </>
  );
}

export default Login;
