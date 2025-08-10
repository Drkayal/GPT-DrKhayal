import React from "react";
import { useParams } from "react-router";
import { TabContent } from "#/components/layout/tab-content";
import ChangesTab from "./changes-tab";
import BrowserTab from "./browser-tab";
import JupyterTab from "./jupyter-tab";
import ServedTab from "./served-tab";
import TerminalTab from "./terminal-tab";
import VSCodeTab from "./vscode-tab";
import { SimpleChat } from "#/components/features/chat/simple-chat";

export default function ConversationRoute() {
  const { conversationId } = useParams<{ conversationId: string }>();

  if (!conversationId) return null;

  return (
    <TabContent
      tabs={[
        { id: "changes", label: "Changes", element: <ChangesTab /> },
        { id: "browser", label: "Browser", element: <BrowserTab /> },
        { id: "jupyter", label: "Jupyter", element: <JupyterTab /> },
        { id: "served", label: "Served", element: <ServedTab /> },
        { id: "terminal", label: "Terminal", element: <TerminalTab /> },
        { id: "vscode", label: "VSCode", element: <VSCodeTab /> },
        { id: "chat", label: "Chat", element: <SimpleChat conversationId={conversationId} /> },
      ]}
    />
  );
}
