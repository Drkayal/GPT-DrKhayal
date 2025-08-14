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
  const [jobStatus, setJobStatus] = React.useState<string | null>(null);
  const [imageUrl, setImageUrl] = React.useState<string | null>(null);
  const [videoUrl, setVideoUrl] = React.useState<string | null>(null);

  const pollJob = async (jobId: string) => {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      // eslint-disable-next-line no-await-in-loop
      const j = await getJob(jobId);
      if (j.status === "COMPLETED") return j.result;
      if (j.status === "FAILED") throw new Error(j.error || "Job failed");
      // eslint-disable-next-line no-await-in-loop
      await new Promise((r) => setTimeout(r, 800));
    }
  };

  const generateImage = async () => {
    if (!imagePrompt.trim()) return;
    // eslint-disable-next-line i18next/no-literal-string
    setJobStatus("Creating image...");
    setImageUrl(null);
    try {
      const jobId = await startImageJob(imagePrompt);
      const result = await pollJob(jobId);
      setImageUrl(result?.path || null);
      // eslint-disable-next-line i18next/no-literal-string
      setJobStatus("Image ready");
    } catch (e) {
      // eslint-disable-next-line i18next/no-literal-string
      setJobStatus("Image generation failed");
    }
  };

  const generateVideo = async () => {
    if (!videoPrompt.trim()) return;
    // eslint-disable-next-line i18next/no-literal-string
    setJobStatus("Creating video...");
    setVideoUrl(null);
    try {
      const jobId = await startVideoJob(videoPrompt);
      const result = await pollJob(jobId);
      setVideoUrl(result?.path || null);
      // eslint-disable-next-line i18next/no-literal-string
      setJobStatus("Video ready");
    } catch (e) {
      // eslint-disable-next-line i18next/no-literal-string
      setJobStatus("Video generation failed");
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 w-full h-full overflow-auto">
      {/* eslint-disable-next-line i18next/no-literal-string */}
      <h1 className="text-2xl font-semibold text-white">General AI Chat</h1>

      {isFetching ? (
        <div className="flex items-center gap-2 text-[#9099AC]">
          <LoadingSpinner size="small" /> {t("LOADING$SETTINGS")}
        </div>
      ) : (
        // eslint-disable-next-line i18next/no-literal-string
        <div className="text-[#9099AC] text-sm">
          {/* eslint-disable-next-line i18next/no-literal-string */}
          Model:{" "}
          <span className="text-white">
            {settings?.LLM_MODEL || "(not set)"}
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
              placeholder="Ask anything..."
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
          {/* eslint-disable-next-line i18next/no-literal-string */}
          <h2 className="text-white font-medium mb-2">Generate Image</h2>
          {/* eslint-disable-next-line i18next/no-literal-string */}
          <input
            value={imagePrompt}
            onChange={(e) => setImagePrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && generateImage()}
            placeholder={"Describe the image..."}
            className="bg-tertiary border border-[#717888] rounded-sm p-2 text-white"
          />
          {imageUrl && (
            // eslint-disable-next-line i18next/no-literal-string
            <img
              src={imageUrl}
              alt="generated"
              className="max-w-full rounded-sm border border-[#717888]"
            />
          )}

          {/* eslint-disable-next-line i18next/no-literal-string */}
          <h2 className="text-white font-medium mb-2">Generate Video</h2>
          {/* eslint-disable-next-line i18next/no-literal-string */}
          <input
            value={videoPrompt}
            onChange={(e) => setVideoPrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && generateVideo()}
            placeholder={"Describe the video..."}
            className="bg-tertiary border border-[#717888] rounded-sm p-2 text-white"
          />
          {videoUrl && (
            <a
              href={videoUrl}
              target="_blank"
              rel="noreferrer"
              className="text-accent underline"
            >
              {/* eslint-disable-next-line i18next/no-literal-string */}
              Download Video
            </a>
          )}
        </div>
      </section>
    </div>
  );
}
