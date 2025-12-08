import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "舆情分析系统",
  description: "多 Agent 舆情分析系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang='zh-CN'>
      <body className='antialiased'>
        {children}
      </body>
    </html>
  );
}
