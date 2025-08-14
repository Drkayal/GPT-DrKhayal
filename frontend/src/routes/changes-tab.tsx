import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import React from "react";
import { ChangesList } from "#/components/features/diff-viewer/changes-list";
import { useGetGitChanges } from "#/hooks/query/use-get-git-changes";
import { I18nKey } from "#/i18n/declaration";
import { RootState } from "#/store";
import { RUNTIME_INACTIVE_STATES } from "#/types/agent-state";
import { RandomTip } from "#/components/features/tips/random-tip";

function StatusMessage({ children }: React.PropsWithChildren) {
  return (
    <div className="w-full h-full flex flex-col items-center text-center justify-center text-2xl text-tertiary-light">
      {children}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-3 w-full">
      <div className="h-4 bg-[#2c2f36] rounded w-1/3" />
      <div className="h-3 bg-[#2c2f36] rounded w-2/3" />
      <div className="h-3 bg-[#2c2f36] rounded w-5/6" />
    </div>
  );
}

function GitChanges() {
  const { t } = useTranslation();
  const {
    data: gitChanges,
    isSuccess,
    isError,
    isLoading: loadingGitChanges,
  } = useGetGitChanges();

  const [statusMessage, setStatusMessage] = React.useState<string[] | null>(
    null,
  );

  const { curAgentState } = useSelector((state: RootState) => state.agent);
  const runtimeIsActive = !RUNTIME_INACTIVE_STATES.includes(curAgentState);

  React.useEffect(() => {
    if (!runtimeIsActive) {
      setStatusMessage([I18nKey.DIFF_VIEWER$WAITING_FOR_RUNTIME]);
    } else if (isError) {
      setStatusMessage([I18nKey.ERROR$GENERIC]);
    } else if (loadingGitChanges) {
      setStatusMessage([I18nKey.DIFF_VIEWER$LOADING]);
    } else {
      setStatusMessage(null);
    }
  }, [runtimeIsActive, isError, loadingGitChanges]);

  const showSkeleton = loadingGitChanges && !isSuccess;

  return (
    <main className="h-full overflow-y-scroll px-4 py-3 gap-3 flex flex-col items-center">
      <div className="card-glow-accent p-4 w-full">
        {showSkeleton && (
          <div className="space-y-4">
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
        )}
        {!showSkeleton && (!isSuccess || !gitChanges.length) && (
          <div className="relative flex h-full w-full items-center">
            <div className="absolute inset-x-0 top-1/2 -translate-y-1/2">
              {statusMessage && (
                <StatusMessage>
                  {statusMessage.map((msg) => (
                    <span key={msg}>{t(msg)}</span>
                  ))}
                </StatusMessage>
              )}
            </div>

            <div className="absolute inset-x-0 bottom-0">
              {!isError && gitChanges?.length === 0 && (
                <div className="max-w-2xl mb-4 text-m bg-tertiary rounded-xl p-4 text-left mx-auto">
                  <RandomTip />
                </div>
              )}
            </div>
          </div>
        )}
        {!showSkeleton && isSuccess && gitChanges.length > 0 && <ChangesList />}
      </div>
    </main>
  );
}

export default GitChanges;
