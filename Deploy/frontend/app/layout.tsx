import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import Sidebar from "@/components/Sidebar";
import UserProfileDropdown from "@/components/UserProfileDropdown";

export const metadata: Metadata = {
  title: "Maya - Analytics Assistant",
  description: "Analytics Assistant per Setera Centralino",
  icons: {
    icon: [
      { url: '/favicon.png', type: 'image/png' },
    ],
    apple: [
      { url: '/favicon.png', sizes: '180x180', type: 'image/png' },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body>
        <AuthProvider>
          <Sidebar />
          <UserProfileDropdown />
          <main className="min-h-screen sidebar-content">
            {children}
          </main>
        </AuthProvider>
      </body>
    </html>
  );
}
