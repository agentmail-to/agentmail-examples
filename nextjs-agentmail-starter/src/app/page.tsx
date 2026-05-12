"use client";

import { useState, useEffect } from "react";

interface Inbox {
  id: string;
  email: string;
  display_name: string;
}

export default function Dashboard() {
  const [inboxes, setInboxes] = useState<Inbox[]>([]);
  const [selectedInbox, setSelectedInbox] = useState<string>("");
  const [newInboxName, setNewInboxName] = useState("");
  const [composeTo, setComposeTo] = useState("");
  const [composeSubject, setComposeSubject] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetchInboxes();
  }, []);

  async function fetchInboxes() {
    const res = await fetch("/api/agentmail/inboxes");
    const data = await res.json();
    setInboxes(data.data || []);
  }

  async function createInbox() {
    const res = await fetch("/api/agentmail/inboxes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ displayName: newInboxName }),
    });
    if (res.ok) {
      setNewInboxName("");
      fetchInboxes();
      setStatus("Inbox created");
    }
  }

  async function sendMessage() {
    if (!selectedInbox || !composeTo || !composeSubject || !composeBody) {
      setStatus("Fill in all fields");
      return;
    }
    const res = await fetch("/api/agentmail/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inboxId: selectedInbox,
        to: composeTo,
        subject: composeSubject,
        text: composeBody,
      }),
    });
    if (res.ok) {
      setComposeTo("");
      setComposeSubject("");
      setComposeBody("");
      setStatus("Message sent");
    } else {
      setStatus("Failed to send");
    }
  }

  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: 40, fontFamily: "system-ui" }}>
      <h1>AgentMail Dashboard</h1>

      <section style={{ marginBottom: 40 }}>
        <h2>Inboxes</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <input
            placeholder="Inbox name"
            value={newInboxName}
            onChange={(e) => setNewInboxName(e.target.value)}
            style={{ padding: 8, flex: 1 }}
          />
          <button onClick={createInbox} style={{ padding: "8px 16px" }}>
            Create Inbox
          </button>
        </div>
        <ul>
          {inboxes.map((inbox) => (
            <li key={inbox.id} style={{ marginBottom: 8 }}>
              <strong>{inbox.display_name}</strong> ({inbox.email})
              <button
                onClick={() => setSelectedInbox(inbox.id)}
                style={{ marginLeft: 8, padding: "4px 8px" }}
              >
                Select
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section style={{ marginBottom: 40 }}>
        <h2>Compose</h2>
        {selectedInbox ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <input
              placeholder="To (email address)"
              value={composeTo}
              onChange={(e) => setComposeTo(e.target.value)}
              style={{ padding: 8 }}
            />
            <input
              placeholder="Subject"
              value={composeSubject}
              onChange={(e) => setComposeSubject(e.target.value)}
              style={{ padding: 8 }}
            />
            <textarea
              placeholder="Message body"
              value={composeBody}
              onChange={(e) => setComposeBody(e.target.value)}
              rows={6}
              style={{ padding: 8 }}
            />
            <button onClick={sendMessage} style={{ padding: "8px 16px", alignSelf: "flex-start" }}>
              Send
            </button>
          </div>
        ) : (
          <p>Select an inbox above to compose a message.</p>
        )}
      </section>

      {status && <p style={{ color: "#666" }}>{status}</p>}
    </main>
  );
}
