import { useState } from "react";
import type { Message } from "./types";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import { clearHistory } from "./api/client";

const SESSION_ID = "rag_" + Math.random().toString(36).slice(2, 8);

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);

  async function handleClearChat() {
    setMessages([]);
    await clearHistory(SESSION_ID).catch(() => {});
  }

  return (
    <div className="flex h-screen overflow-hidden bg-base text-txt mesh-bg">
      <Sidebar
        sessionId={SESSION_ID}
        onClearChat={handleClearChat}
      />
      <main className="flex-1 min-w-0 h-full">
        <ChatPanel
          sessionId={SESSION_ID}
          messages={messages}
          setMessages={setMessages}
        />
      </main>
    </div>
  );
}
