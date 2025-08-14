import React from "react";
import { useTranslation } from "react-i18next";
import { BrandButton } from "#/components/features/settings/brand-button";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { useSettings } from "#/hooks/query/use-settings";
import { streamChat, startImageJob, startVideoJob, getJob } from "#/api/chat";

export default function ChatRoute() {
  const { t } = useTranslation();
  const { data: settings, isFetching } = useSettings();

  const [prompt, setPrompt] = React.useState("");
  const [messages, setMessages] = React.useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);
  const [isSending, setIsSending] = React.useState(false);

  const sendMessage = async () => {
    if (!prompt.trim()) return;
    const userMsg = { role: "user" as const, content: prompt };
    setMessages((m) => [...m, userMsg, { role: "assistant", content: "" }]);
    setPrompt("");
    setIsSending(true);
    try {
      await streamChat(
        [{ role: "user", content: userMsg.content }],
        settings?.LLM_MODEL,
        (token) => {
          setMessages((prev) => {
            const copy = [...prev];
            // append to last assistant message
            const lastIdx = copy.length - 1;
            if (lastIdx >= 0 && copy[lastIdx].role === "assistant") {
              copy[lastIdx] = {
                ...copy[lastIdx],
                content: copy[lastIdx].content + token,
              };
            }
            return copy;
          });
        },
      );
    } finally {
      setIsSending(false);
    }
  };

  const [imagePrompt, setImagePrompt] = React.useState("");
  const [videoPrompt, setVideoPrompt] = React.useState("");
  const [imageUrl, setImageUrl] = React.useState<string | null>(null);
  const [videoUrl, setVideoUrl] = React.useState<string | null>(null);

  const pollJob = async (jobId: string) => {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      // eslint-disable-next-line no-await-in-loop
      const j = await getJob(jobId);
      if (j.status === "COMPLETED") return j.result;
      if (j.status === "FAILED") throw new Error(j.error || "Job failed");
      // eslint-disable-next-line no-await-in-loop, no-promise-executor-return
      await new Promise<void>((resolve) => setTimeout(resolve, 800));
    }
  };

  const generateImage = async () => {
    if (!imagePrompt.trim()) return;
    setImageUrl(null);
    try {
      const jobId = await startImageJob(imagePrompt);
      const result = await pollJob(jobId);
      setImageUrl(result?.path || null);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error(e);
    }
  };

  const generateVideo = async () => {
    if (!videoPrompt.trim()) return;
    setVideoUrl(null);
    try {
      const jobId = await startVideoJob(videoPrompt);
      const result = await pollJob(jobId);
      setVideoUrl(result?.path || null);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error(e);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 w-full h-full overflow-auto">
      <h1 className="text-2xl font-semibold text-white">{t("CHAT$TITLE")}</h1>

      {isFetching ? (
        <div className="flex items-center gap-2 text-[#9099AC]">
          <LoadingSpinner size="small" /> {t("LOADING$SETTINGS")}
        </div>
      ) : (
        <div className="text-[#9099AC] text-sm">
          {t("CHAT$MODEL_LABEL")}{" "}
          <span className="text-white">
            {settings?.LLM_MODEL || t("CHAT$MODEL_NOT_SET")}
          </span>
        </div>
      )}

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="col-span-2 card-glow-accent p-4 h-[60vh] flex flex-col">
          <div className="flex-1 overflow-auto flex flex-col gap-3 pr-1">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={m.role === "user" ? "text-white" : "text-glow"}
              >
                <span className="text-xs opacity-70 mr-2">{m.role}</span>
                {m.content}
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 mt-3">
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder={t("CHAT$ASK_ANYTHING")}
              className="flex-1 bg-tertiary border border-[#717888] rounded-sm p-2 text-white"
            />
            <BrandButton
              variant="primary"
              type="button"
              onClick={sendMessage}
              isDisabled={isSending || !prompt.trim()}
              className="btn-3d"
            >
              {isSending ? t("SENDING") : t("SEND")}
            </BrandButton>
          </div>
        </div>

        <div className="col-span-1 flex flex-col gap-4">
          <h2 className="text-white font-medium mb-2">
            {t("CHAT$GENERATE_IMAGE")}
          </h2>
          <input
            value={imagePrompt}
            onChange={(e) => setImagePrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && generateImage()}
            placeholder={t("CHAT$DESCRIBE_IMAGE")}
            className="bg-tertiary border border-[#717888] rounded-sm p-2 text-white"
          />
          {imageUrl && (
            <img
              src={imageUrl}
              alt={t("CHAT$GENERATED_IMAGE_ALT")}
              className="max-w-full rounded-sm border border-[#717888]"
            />
          )}

          <h2 className="text-white font-medium mb-2">
            {t("CHAT$GENERATE_VIDEO")}
          </h2>
          <input
            value={videoPrompt}
            onChange={(e) => setVideoPrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && generateVideo()}
            placeholder={t("CHAT$DESCRIBE_VIDEO")}
            className="bg-tertiary border border-[#717888] rounded-sm p-2 text-white"
          />
          {videoUrl && (
            <a
              href={videoUrl}
              target="_blank"
              rel="noreferrer"
              className="text-accent underline"
            >
              {t("CHAT$DOWNLOAD_VIDEO")}
            </a>
          )}
        </div>
      </section>
    </div>
  );
}
