'use client';

import { useTheme, ThemeMode } from '../hooks/useTheme';

const themes: { mode: ThemeMode; icon: string; label: string }[] = [
  { mode: 'light', icon: '☀️', label: '亮色' },
  { mode: 'dark', icon: '🌙', label: '暗色' },
  { mode: 'auto', icon: '🌓', label: '自动' },
];

export function ThemeSwitcher() {
  const { mode, setMode } = useTheme();

  return (
    <div className='flex items-center gap-1 bg-violet-100 dark:bg-slate-800 rounded-lg p-0.5'>
      {themes.map((theme) => (
        <button
          key={theme.mode}
          onClick={() => setMode(theme.mode)}
          title={theme.label}
          className={`px-2 py-1 rounded-md text-xs font-medium transition-all flex items-center gap-1 ${
            mode === theme.mode
              ? 'bg-white dark:bg-slate-700 text-violet-700 dark:text-white shadow-sm'
              : 'text-violet-500 dark:text-slate-400 hover:text-violet-700 dark:hover:text-white'
          }`}
        >
          <span>{theme.icon}</span>
          <span className='hidden sm:inline'>{theme.label}</span>
        </button>
      ))}
    </div>
  );
}
