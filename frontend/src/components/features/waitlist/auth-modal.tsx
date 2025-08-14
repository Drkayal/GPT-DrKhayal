import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import AllHandsLogo from "#/assets/branding/all-hands-logo.svg?react";
import { ModalBackdrop } from "#/components/shared/modals/modal-backdrop";
import { ModalBody } from "#/components/shared/modals/modal-body";
import { BrandButton } from "../settings/brand-button";
import GitHubLogo from "#/assets/branding/github-logo.svg?react";
import { GetConfigResponse } from "#/api/open-hands.types";
import { Provider } from "#/types/settings";

interface AuthModalProps {
  githubAuthUrl: string | null;
  appMode?: GetConfigResponse["APP_MODE"] | null;
  authUrl?: GetConfigResponse["AUTH_URL"];
  providersConfigured?: Provider[];
}

export function AuthModal({
  githubAuthUrl,
  appMode,
  authUrl,
  providersConfigured,
}: AuthModalProps) {
  const { t } = useTranslation();

  const handleGitHubAuth = () => {
    if (githubAuthUrl) {
      // Always start the OIDC flow, let the backend handle TOS check
      window.location.href = githubAuthUrl;
    } else {
      window.location.href = "/api/auth/github/start";
    }
  };

  // Only show buttons if providers are configured and include the specific provider
  const showGithub =
    providersConfigured &&
    providersConfigured.length > 0 &&
    providersConfigured.includes("github");

  // Check if no providers are configured
  const noProvidersConfigured =
    !providersConfigured || providersConfigured.length === 0;

  return (
    <ModalBackdrop>
      <ModalBody className="border border-tertiary">
        <AllHandsLogo width={68} height={46} />
        <div className="flex flex-col gap-2 w-full items-center text-center">
          <h1 className="text-2xl font-bold">
            {t(I18nKey.AUTH$SIGN_IN_WITH_IDENTITY_PROVIDER)}
          </h1>
        </div>

        <div className="flex flex-col gap-3 w-full">
          {noProvidersConfigured ? (
            <div className="text-center p-4 text-muted-foreground">
              {t(I18nKey.AUTH$NO_PROVIDERS_CONFIGURED)}
            </div>
          ) : (
            <>
              {showGithub && (
                <BrandButton
                  type="button"
                  variant="primary"
                  onClick={handleGitHubAuth}
                  className="w-full"
                  startContent={<GitHubLogo width={20} height={20} />}
                >
                  {t(I18nKey.GITHUB$CONNECT_TO_GITHUB)}
                </BrandButton>
              )}
            </>
          )}
        </div>

        <p
          className="mt-4 text-xs text-center text-muted-foreground"
          data-testid="auth-modal-terms-of-service"
        >
          {t(I18nKey.AUTH$BY_SIGNING_UP_YOU_AGREE_TO_OUR)}{" "}
          <a
            href="https://www.all-hands.dev/tos"
            target="_blank"
            className="underline hover:text-primary"
            rel="noopener noreferrer"
          >
            {t(I18nKey.COMMON$TERMS_OF_SERVICE)}
          </a>{" "}
          {t(I18nKey.COMMON$AND)}{" "}
          <a
            href="https://www.all-hands.dev/privacy"
            target="_blank"
            className="underline hover:text-primary"
            rel="noopener noreferrer"
          >
            {t(I18nKey.COMMON$PRIVACY_POLICY)}
          </a>
          .
        </p>
      </ModalBody>
    </ModalBackdrop>
  );
}
