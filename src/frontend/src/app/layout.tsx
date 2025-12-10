import type { Metadata } from "next";
import { ThemeProvider } from "../hooks/useTheme";
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
    <html lang='zh-CN' suppressHydrationWarning>
      <head>
        {/* 防止主题闪烁的内联脚本 */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var mode = localStorage.getItem('theme-mode');
                  var theme = mode;
                  if (mode === 'auto' || !mode) {
                    theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                  }
                  document.documentElement.classList.add(theme);
                } catch (e) {
                  document.documentElement.classList.add('dark');
                }
              })();
            `,
          }}
        />
      </head>
      <body className='antialiased'>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
