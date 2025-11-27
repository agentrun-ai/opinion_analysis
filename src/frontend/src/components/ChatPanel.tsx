'use client';

import { useState, useRef, useEffect } from 'react';
import type { Message } from '@ag-ui/client';

interface ChatPanelProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  running: boolean;
  error: string | null;
}

export function ChatPanel({ messages, onSendMessage, running, error }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || running) return;
    
    onSendMessage(input.trim());
    setInput('');
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-cyan-800/30 rounded-lg overflow-hidden">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-slate-500 py-8">
            <p className="text-lg mb-2">👋 欢迎使用舆情分析系统</p>
            <p className="text-sm">输入关键词开始分析，例如：</p>
            <p className="text-sm text-cyan-400 mt-2">{'"'}分析{`'`}新能源汽车{`'`}的舆情{'"'}</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.role === 'user'
                    ? 'bg-cyan-600 text-white'
                    : 'bg-slate-800 text-slate-200 border border-slate-700'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content || '...'}</p>
              </div>
            </div>
          ))
        )}
        
        {/* 运行中指示器 */}
        {running && (
          <div className="flex justify-start">
            <div className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2">
              <div className="flex items-center gap-2">
                <div className="animate-spin h-4 w-4 border-2 border-cyan-400 border-t-transparent rounded-full" />
                <span className="text-sm text-slate-400">正在分析...</span>
              </div>
            </div>
          </div>
        )}
        
        {/* 错误提示 */}
        {error && (
          <div className="bg-red-900/30 border border-red-500/50 rounded-lg px-4 py-2">
            <p className="text-sm text-red-400">❌ {error}</p>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-slate-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入关键词开始分析..."
            disabled={running}
            className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={running || !input.trim()}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-medium transition-colors"
          >
            {running ? '分析中...' : '发送'}
          </button>
        </div>
      </form>
    </div>
  );
}

