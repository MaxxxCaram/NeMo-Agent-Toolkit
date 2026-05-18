import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IPL M22 Assistant",
  description: "Decision-support UI (connects to your GraphQL API)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
