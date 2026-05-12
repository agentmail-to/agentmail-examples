export const metadata = {
  title: "AgentMail Dashboard",
  description: "Manage AI agent email inboxes",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
