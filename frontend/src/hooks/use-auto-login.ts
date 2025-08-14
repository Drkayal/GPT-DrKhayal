import { useEffect } from "react";
import { useConfig } from "./query/use-config";
import { useIsAuthed } from "./query/use-is-authed";
import { getLoginMethod, LoginMethod } from "#/utils/local-storage";

/**
 * Hook to automatically log in the user if they have a login method stored in local storage
 * Only works in SAAS mode and when the user is not already logged in
 */
export const useAutoLogin = () => {
  const { data: config, isLoading: isConfigLoading } = useConfig();
  const { data: isAuthed, isLoading: isAuthLoading } = useIsAuthed();

  // Get the stored login method
  const loginMethod = getLoginMethod();

  useEffect(() => {
    // Only auto-login in SAAS mode
    if (config?.APP_MODE !== "saas") {
      return;
    }

    // Wait for auth and config to load
    if (isConfigLoading || isAuthLoading) {
      return;
    }

    // Don't auto-login if already authenticated
    if (isAuthed) {
      return;
    }

    // Only support GitHub auto-login path; other providers are not configured
    if (loginMethod === LoginMethod.GITHUB) {
      window.location.href = "/api/auth/github/start";
    }
  }, [config?.APP_MODE, isAuthed, isConfigLoading, isAuthLoading, loginMethod]);
};
