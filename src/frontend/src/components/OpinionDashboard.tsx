'use client';

import { AgentState } from '../lib/types';
import { useAgentState } from '../hooks/useAgentState';
import { ChatPanel } from './ChatPanel';
import { useEffect, useRef } from 'react';

export function OpinionDashboard() {
  const { state, setState, running, sendMessage, messages, error } =
    useAgentState<AgentState>({
      name: 'opinion_agent',
      agentUrl: 'c410d179b056797269a4a2188bdf8a48', // 末尾需要斜杠，因为 AG-UI 挂载在 /api/agent
      initialState: {
        keyword: '',
        status: 'idle',
        logs: [],
        max_results: 5,
        batch_size: 20,
        raw_data: [],
        collected_data_summary: [],
        batch_analyses: [],
        analysis: null,
        report_text: '',
        final_html: '',
      },
    });

  const logsEndRef = useRef<HTMLDivElement>(null);

  // 调试：监听状态变化
  useEffect(() => {
    console.log('🔍 [DEBUG] State updated:', {
      status: state.status,
      keyword: state.keyword,
      collected_data_summary_count: state.collected_data_summary?.length || 0,
      raw_data_count: state.raw_data?.length || 0,
      collected_data_summary: state.collected_data_summary,
    });
  }, [state]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.logs]);

  return (
    <div className='min-h-screen bg-slate-950 text-cyan-50 font-mono p-4 md:p-8 overflow-hidden flex flex-col'>
      {/* Header */}
      <header className='mb-8 border-b border-cyan-900/50 pb-4 flex justify-between items-center'>
        <div>
          <h1 className='text-2xl md:text-3xl font-bold tracking-wider text-transparent bg-clip-text bg-linear-to-r from-cyan-400 to-blue-600'>
            舆情分析系统
          </h1>
          <p className='text-xs text-slate-500 mt-1'>
            基于 AG-UI 协议 · 直接 HTTP SSE 通信
          </p>
        </div>
        <div className='text-right hidden md:block'>
          <div
            className={`inline-block px-3 py-1 rounded-full text-xs font-bold border ${
              state.status === 'complete'
                ? 'border-green-500 text-green-400'
                : state.status === 'idle'
                ? 'border-slate-700 text-slate-500'
                : 'border-cyan-500 text-cyan-400 animate-pulse'
            }`}
          >
            STATUS: {state.status.toUpperCase()}
          </div>
        </div>
      </header>

      <div className='flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 overflow-hidden'>
        {/* Left Column: Chat & Controls */}
        <div className='lg:col-span-4 flex flex-col gap-6 overflow-hidden max-h-[calc(100vh-200px)]'>
          {/* Chat Panel */}
          <div className='flex-1 min-h-[300px]'>
            <ChatPanel
              messages={messages}
              onSendMessage={sendMessage}
              running={running}
              error={error}
            />
          </div>

          {/* Configuration */}
          <div className='bg-linear-to-br from-cyan-900/20 to-blue-900/20 border border-cyan-500/30 p-4 rounded-xl backdrop-blur-sm'>
            <h2 className='text-sm font-semibold text-cyan-300 mb-3 uppercase flex items-center gap-2'>
              <span className='w-2 h-2 bg-cyan-400 rounded-full'></span>
              配置选项
            </h2>

            {/* Max Results Configuration */}
            <div className='mb-3'>
              <label className='text-xs text-slate-500 mb-1 block'>
                最大采集数量
              </label>
              <input
                type='number'
                min='5'
                max='200'
                value={state.max_results}
                onChange={(e) =>
                  setState({
                    ...state,
                    max_results: Math.max(
                      5,
                      Math.min(200, parseInt(e.target.value) || 100)
                    ),
                  })
                }
                className='w-full bg-slate-950 text-cyan-300 border border-cyan-900/50 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50'
              />
            </div>

            {/* Batch Size Configuration */}
            <div>
              <label className='text-xs text-slate-500 mb-1 block'>
                分批分析大小
              </label>
              <input
                type='number'
                min='10'
                max='50'
                value={state.batch_size}
                onChange={(e) =>
                  setState({
                    ...state,
                    batch_size: Math.max(
                      10,
                      Math.min(50, parseInt(e.target.value) || 20)
                    ),
                  })
                }
                className='w-full bg-slate-950 text-cyan-300 border border-cyan-900/50 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50'
              />
            </div>
          </div>

          {/* Collected Data */}
          {state.collected_data_summary &&
            state.collected_data_summary.length > 0 && (
              <div className='bg-slate-900/50 border border-cyan-900/30 rounded-xl p-4 max-h-48 overflow-hidden flex flex-col'>
                <h2 className='text-sm font-semibold text-cyan-300 mb-3 uppercase flex items-center gap-2'>
                  <span className='w-2 h-2 bg-green-400 rounded-full animate-pulse'></span>
                  已收集数据 ({state.collected_data_summary.length})
                </h2>
                <div className='flex-1 overflow-y-auto space-y-2 pr-2 scrollbar-thin scrollbar-thumb-cyan-900 scrollbar-track-transparent'>
                  {state.collected_data_summary.map((item, i) => (
                    <div
                      key={i}
                      className='bg-black/40 rounded p-2 border border-slate-800 hover:border-cyan-700 transition-colors'
                    >
                      <a
                        href={item.url}
                        target='_blank'
                        rel='noopener noreferrer'
                        className='text-cyan-400 hover:text-cyan-300 text-xs font-medium line-clamp-1 flex items-center gap-1'
                      >
                        {item.title}
                        <svg
                          className='w-3 h-3 shrink-0'
                          fill='none'
                          stroke='currentColor'
                          viewBox='0 0 24 24'
                        >
                          <path
                            strokeLinecap='round'
                            strokeLinejoin='round'
                            strokeWidth={2}
                            d='M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14'
                          />
                        </svg>
                      </a>
                      <div className='mt-1'>
                        <span className='text-[9px] text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded'>
                          {item.source}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          {/* System Logs */}
          <div className='bg-black/80 border border-slate-800 rounded-xl p-4 font-mono text-xs overflow-hidden flex flex-col min-h-[150px] max-h-[200px]'>
            <h2 className='text-slate-400 mb-2 pb-2 border-b border-slate-800 flex justify-between'>
              <span>SYSTEM LOGS</span>
              <span className='text-cyan-500 animate-pulse'>● LIVE</span>
            </h2>
            <div className='flex-1 overflow-y-auto space-y-1 pr-2 scrollbar-thin scrollbar-thumb-cyan-900 scrollbar-track-transparent'>
              {state.logs.length === 0 && (
                <span className='text-slate-700 italic'>
                  System idle. Waiting for instructions...
                </span>
              )}
              {state.logs.map((log, i) => (
                <div key={i} className='text-slate-300 break-words'>
                  <span className='text-cyan-700 mr-2'>{'>'}</span>
                  {log}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>

        {/* Right Column: Visualization / Report */}
        <div className='lg:col-span-8 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden relative flex flex-col'>
          <div className='absolute inset-0 bg-[linear-gradient(rgba(6,182,212,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(6,182,212,0.05)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none'></div>

          <div className='p-4 border-b border-slate-800 bg-slate-950/50 backdrop-blur flex justify-between items-center z-10'>
            <h2 className='text-sm font-bold text-white flex items-center gap-2'>
              REPORT VIEW
              {state.keyword && (
                <span className='text-cyan-500 px-2 py-0.5 bg-cyan-950/50 rounded text-xs border border-cyan-900'>
                  TARGET: {state.keyword}
                </span>
              )}
            </h2>
          </div>

          <div className='flex-1 overflow-y-auto bg-white/5 p-4 relative z-0'>
            {state.final_html ? (
              <div className='bg-white w-full h-full min-h-[600px] rounded shadow-2xl overflow-hidden'>
                <iframe
                  srcDoc={state.final_html}
                  className='w-full h-full border-0'
                  title='Analysis Report'
                />
              </div>
            ) : (
              <div className='h-full flex flex-col items-center justify-center text-slate-400 gap-6 p-8'>
                {/* 状态指示器 */}
                <div className='w-20 h-20 relative'>
                  <div className='absolute inset-0 border-4 border-slate-700 rounded-full'></div>
                  <div className='absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin'></div>
                  <div className='absolute inset-0 flex items-center justify-center'>
                    <div className='w-12 h-12 bg-cyan-500/20 rounded-full animate-pulse'></div>
                  </div>
                </div>

                {/* 当前状态 */}
                <div className='text-center'>
                  <p className='text-xl font-semibold text-white mb-2'>
                    {state.status === 'idle' && '等待开始分析...'}
                    {state.status === 'collecting' && '🔍 正在收集数据...'}
                    {state.status === 'collected' && '✅ 数据收集完成'}
                    {state.status === 'analyzing' && '📊 正在分析数据...'}
                    {state.status === 'analyzed' && '✅ 数据分析完成'}
                    {state.status === 'writing' && '📝 正在撰写报告...'}
                    {state.status === 'written' && '✅ 报告撰写完成'}
                    {state.status === 'rendering' && '🎨 正在渲染 HTML...'}
                  </p>

                  {/* 进度提示 */}
                  {state.keyword && (
                    <p className='text-sm text-slate-500'>
                      关键词:{' '}
                      <span className='text-cyan-400'>{state.keyword}</span>
                    </p>
                  )}
                </div>

                {/* 收集进度 */}
                {state.collected_data_summary &&
                  state.collected_data_summary.length > 0 && (
                    <div className='w-full max-w-md'>
                      <div className='bg-slate-800/50 rounded-lg p-4 border border-slate-700'>
                        <div className='flex items-center justify-between mb-2'>
                          <span className='text-sm text-slate-400'>
                            已收集数据
                          </span>
                          <span className='text-lg font-bold text-cyan-400'>
                            {state.collected_data_summary.length} /{' '}
                            {state.max_results}
                          </span>
                        </div>
                        <div className='w-full bg-slate-700 rounded-full h-2 overflow-hidden'>
                          <div
                            className='bg-gradient-to-r from-cyan-500 to-blue-500 h-full transition-all duration-500 ease-out'
                            style={{
                              width: `${Math.min(
                                (state.collected_data_summary.length /
                                  state.max_results) *
                                  100,
                                100
                              )}%`,
                            }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  )}

                {/* 分析进度 */}
                {state.analysis && (
                  <div className='w-full max-w-md'>
                    <div className='bg-slate-800/50 rounded-lg p-4 border border-slate-700'>
                      <div className='text-sm text-slate-400 mb-2'>
                        分析结果预览
                      </div>
                      <div className='grid grid-cols-3 gap-3 text-center'>
                        <div>
                          <div className='text-lg font-bold text-green-400'>
                            {state.analysis.sentiment_distribution?.['正面'] ||
                              0}
                            %
                          </div>
                          <div className='text-xs text-slate-500'>正面</div>
                        </div>
                        <div>
                          <div className='text-lg font-bold text-yellow-400'>
                            {state.analysis.sentiment_distribution?.['中性'] ||
                              0}
                            %
                          </div>
                          <div className='text-xs text-slate-500'>中性</div>
                        </div>
                        <div>
                          <div className='text-lg font-bold text-red-400'>
                            {state.analysis.sentiment_distribution?.['负面'] ||
                              0}
                            %
                          </div>
                          <div className='text-xs text-slate-500'>负面</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 最新日志 */}
                {state.logs.length > 0 && (
                  <div className='text-xs text-slate-600 max-w-md text-center'>
                    {state.logs[state.logs.length - 1]}
                  </div>
                )}

                {/* 提示信息 */}
                {state.status === 'idle' && (
                  <div className='text-center text-sm text-slate-600 max-w-md'>
                    <p>💡 提示：在左侧聊天框输入关键词开始分析</p>
                    <p className='mt-2'>
                      例如：分析&apos;新能源汽车&apos;的舆情
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
