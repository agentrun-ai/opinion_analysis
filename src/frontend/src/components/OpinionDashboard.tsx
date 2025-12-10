'use client';

import { AgentState } from '../lib/types';
import { useAgentState } from '../hooks/useAgentState';
import dynamic from 'next/dynamic';
import { useEffect, useRef, useState } from 'react';
import { ENDPOINT } from '@/lib/const';
import { ThemeSwitcher } from './ThemeSwitcher';

// 动态导入 VncViewer，禁用 SSR（noVNC 需要浏览器环境）
const VncViewer = dynamic(
  () => import('./VncViewer').then((mod) => ({ default: mod.VncViewer })),
  {
    ssr: false,
    loading: () => (
      <div className='w-full h-full flex items-center justify-center bg-slate-50 dark:bg-black'>
        <div className='flex flex-col items-center gap-4'>
          <div className='w-12 h-12 border-4 border-blue-500 dark:border-cyan-500 border-t-transparent rounded-full animate-spin'></div>
          <span className='text-blue-600 dark:text-cyan-400 text-sm'>加载 VNC 组件...</span>
        </div>
      </div>
    ),
  }
);

// Tab 类型
type TabType = 'browser' | 'analysis' | 'report';

export function OpinionDashboard() {
  const { state, setState, running, sendMessage, error } =
    useAgentState<AgentState>({
      name: 'opinion_agent',
      agentUrl: `${ENDPOINT}/api/agent`,
      initialState: {
        keyword: '',
        status: 'idle',
        logs: [],
        max_results: 50,
        raw_data: [],
        collected_data_summary: [],
        analysis: null,
        report_text: '',
        final_html: '',
        collection_progress: 0,
        current_phase: '',
      },
    });

  // 关键词输入
  const [keyword, setKeyword] = useState('');
  const logsEndRef = useRef<HTMLDivElement>(null);

  // 当前选中的 Tab
  const [activeTab, setActiveTab] = useState<TabType>('browser');

  // 自动滚动到底部的 ref
  const analysisEndRef = useRef<HTMLDivElement>(null);

  // 当前选中显示的 Sandbox ID（用于 VNC 切换）
  const [selectedSandboxId, setSelectedSandboxId] = useState<string | null>(null);

  // 调试：监听状态变化
  useEffect(() => {
    console.log('🔍 [DEBUG] State updated:', {
      status: state.status,
      keyword: state.keyword,
      collected_data_summary_count: state.collected_data_summary?.length || 0,
      report_text_length: state.report_text?.length || 0,
      final_html_length: state.final_html?.length || 0,
      sandboxes_count: state.sandboxes?.length || 0,
      active_sandbox_id: state.active_sandbox_id,
    });
  }, [state]);

  // 当 active_sandbox_id 变化时，自动切换到新的 sandbox
  useEffect(() => {
    if (state.active_sandbox_id && state.active_sandbox_id !== selectedSandboxId) {
      console.log('🔄 Active sandbox changed from state:', state.active_sandbox_id);
      setSelectedSandboxId(state.active_sandbox_id);
    }
  }, [state.active_sandbox_id, selectedSandboxId]);

  // 处理 sandbox 切换
  const handleSandboxSelect = (sandboxId: string) => {
    console.log('👆 User selected sandbox:', sandboxId);
    setSelectedSandboxId(sandboxId);
  };

  // 根据状态自动切换 Tab
  useEffect(() => {
    if (state.status === 'collecting' || state.status === 'collected') {
      setActiveTab('browser');
    } else if (
      state.status === 'analyzing' ||
      state.status === 'analyzed' ||
      state.status === 'writing' ||
      state.status === 'written' ||
      state.status === 'rendering'
    ) {
      setActiveTab('analysis');
    } else if (state.status === 'complete' && state.final_html) {
      setActiveTab('report');
    }
  }, [state.status, state.final_html]);

  // 自动滚动到分析/报告内容底部（流式效果）
  useEffect(() => {
    if (activeTab === 'analysis') {
      analysisEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [state.analysis, state.report_text, activeTab]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.logs]);

  // 开始分析
  const handleStartAnalysis = () => {
    if (!keyword.trim() || running) return;
    sendMessage(`分析'${keyword.trim()}'的舆情`);
  };

  // 判断当前阶段
  const isCollectingPhase =
    state.status === 'collecting' || state.status === 'collected';
  const isProcessingPhase =
    state.status === 'analyzing' ||
    state.status === 'analyzed' ||
    state.status === 'writing' ||
    state.status === 'written' ||
    state.status === 'rendering';
  const isCompletePhase = state.status === 'complete';
  const hasContent = isCollectingPhase || isProcessingPhase || isCompletePhase;

  // Tab 配置
  const tabs: {
    id: TabType;
    label: string;
    icon: string;
    available: boolean;
  }[] = [
    {
      id: 'browser',
      label: '浏览器',
      icon: '🌐',
      available:
        isCollectingPhase || (state.collected_data_summary?.length || 0) > 0,
    },
    {
      id: 'analysis',
      label: '分析',
      icon: '📊',
      available:
        isProcessingPhase ||
        isCompletePhase ||
        !!state.analysis ||
        !!state.report_text,
    },
    {
      id: 'report',
      label: '报告',
      icon: '📄',
      available: isCompletePhase && !!state.final_html,
    },
  ];

  return (
    <div className='h-screen bg-linear-to-br bg-red-50 from-sky-50 via-indigo-50/40 to-violet-50/50 dark:from-slate-950 dark:via-slate-950 dark:to-slate-900 text-gray-700 dark:text-cyan-50 font-mono p-4 md:p-6 flex flex-col overflow-hidden'>
      {/* AI 声明 */}
      <div className='bg-orange-50 dark:bg-amber-900/30 border border-orange-200 dark:border-amber-600/50 rounded-lg px-4 py-2 mb-3 shrink-0 shadow-sm'>
        <p className='text-xs text-orange-600 dark:text-amber-300'>
          ⚠️ <strong>免责声明</strong>
          ：内容由AI生成，仅供参考，您据此所作判断及操作均由您自行承担责任。
        </p>
      </div>

      {/* Header */}
      <header className='mb-4 border-b border-indigo-100 dark:border-cyan-900/50 pb-3 flex justify-between items-center shrink-0'>
        <div>
          <h1 className='text-xl md:text-2xl font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 dark:from-cyan-400 dark:to-blue-600'>
            舆情分析系统
          </h1>
          <p className='text-xs text-gray-400 dark:text-slate-500 mt-0.5'>
            实时浏览器预览
          </p>
        </div>
        <div className='flex items-center gap-4'>
          {/* 主题切换 */}
          <ThemeSwitcher />
          {/* 状态指示器 */}
          <div className='text-right hidden md:block'>
            <div
              className={`inline-block px-3 py-1 rounded-full text-xs font-bold border shadow-sm ${
                state.status === 'complete'
                  ? 'border-emerald-300 dark:border-green-500 text-emerald-600 dark:text-green-400 bg-emerald-50 dark:bg-transparent'
                  : state.status === 'idle'
                  ? 'border-gray-200 dark:border-slate-700 text-gray-400 bg-gray-50 dark:bg-transparent'
                  : 'border-violet-300 dark:border-cyan-500 text-violet-600 dark:text-cyan-400 bg-violet-50 dark:bg-transparent animate-pulse'
              }`}
            >
              {state.status === 'idle' && '等待输入'}
              {state.status === 'collecting' &&
                `🔍 数据收集中... ${state.collection_progress || 0}%`}
              {state.status === 'collected' && '✅ 收集完成'}
              {state.status === 'analyzing' && '📊 分析中...'}
              {state.status === 'analyzed' && '✅ 分析完成'}
              {state.status === 'writing' && '📝 撰写中...'}
              {state.status === 'written' && '✅ 撰写完成'}
              {state.status === 'rendering' && '🎨 渲染中...'}
              {state.status === 'complete' && '✅ 完成'}
              {state.current_phase && ` - ${state.current_phase}`}
            </div>
          </div>
        </div>
      </header>

      <div className='flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0'>
        {/* Left Column: 关键词输入 & 配置 & 搜索记录 & 日志 */}
        <div className='lg:col-span-3 flex flex-col gap-3 min-h-0 overflow-hidden'>
          {/* 关键词输入 */}
          <div className='bg-white dark:bg-[unset] dark:bg-linear-to-br dark:from-cyan-900/30 dark:to-blue-900/30 border border-violet-100 dark:border-cyan-500/40 p-4 rounded-xl shadow-sm dark:shadow-none backdrop-blur-sm shrink-0'>
            <h2 className='text-sm font-semibold text-violet-600 dark:text-cyan-300 mb-3 uppercase flex items-center gap-2'>
              <span className='w-2 h-2 bg-violet-500 dark:bg-cyan-400 rounded-full'></span>
              舆情分析
            </h2>

            <div className='space-y-3'>
              {/* 关键词输入框 */}
              <div>
                <label className='text-xs text-gray-500 dark:text-slate-400 mb-1.5 block'>
                  输入分析关键词
                </label>
                <input
                  type='text'
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleStartAnalysis()}
                  placeholder='例如：新能源汽车...'
                  disabled={running}
                  className='w-full bg-gray-50 dark:bg-slate-950/80 text-gray-700 dark:text-cyan-100 border border-gray-200 dark:border-cyan-800/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/40 dark:focus:ring-cyan-500/50 focus:border-violet-400 dark:focus:border-cyan-500 disabled:opacity-50 placeholder:text-gray-400 dark:placeholder:text-slate-600 transition-all'
                />
              </div>

              {/* 最大采集数量 */}
              <div>
                <label className='text-xs text-gray-500 dark:text-slate-400 mb-1.5 block'>
                  最大采集数量
                </label>
                <input
                  type='number'
                  min='5'
                  max='100'
                  value={state.max_results}
                  onChange={(e) =>
                    setState({
                      ...state,
                      max_results: Math.max(
                        5,
                        Math.min(100, parseInt(e.target.value) || 50)
                      ),
                    })
                  }
                  disabled={running}
                  className='w-full bg-gray-50 dark:bg-slate-950/80 text-violet-600 dark:text-cyan-300 border border-gray-200 dark:border-cyan-800/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/40 dark:focus:ring-cyan-500/50 disabled:opacity-50 transition-all'
                />
              </div>

              {/* 开始分析按钮 */}
              <button
                onClick={handleStartAnalysis}
                disabled={running || !keyword.trim()}
                className='w-full bg-gradient-to-r dark:bg-[unset] from-violet-500 via-purple-500 to-fuchsia-500 dark:from-cyan-600 dark:to-blue-600 hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400 dark:hover:from-cyan-500 dark:hover:to-blue-500 disabled:from-gray-300 disabled:via-gray-300 disabled:to-gray-300 dark:disabled:from-slate-700 dark:disabled:to-slate-700 disabled:cursor-not-allowed text-white px-4 py-2.5 rounded-lg font-semibold transition-all shadow-lg shadow-violet-500/25 dark:shadow-cyan-500/20 disabled:shadow-none text-sm'
              >
                {running ? (
                  <span className='flex items-center justify-center gap-2'>
                    <span className='w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin'></span>
                    分析中...
                  </span>
                ) : (
                  '开始分析'
                )}
              </button>
            </div>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className='bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-500/50 rounded-xl px-3 py-2 shrink-0 shadow-sm'>
              <p className='text-xs text-red-600 dark:text-red-400'>
                ❌ {error}
              </p>
            </div>
          )}

          {/* 收集进度 & 搜索记录 */}
          {state.collected_data_summary &&
            state.collected_data_summary.length > 0 && (
              <div className='bg-white dark:bg-slate-900/50 border border-violet-100 dark:border-cyan-900/30 rounded-xl p-3 flex-1 min-h-0 flex flex-col overflow-hidden shadow-sm dark:shadow-none'>
                <div className='flex items-center justify-between mb-2 shrink-0'>
                  <span className='text-xs text-gray-500 dark:text-slate-400 flex items-center gap-1'>
                    <span className='w-1.5 h-1.5 bg-emerald-500 dark:bg-green-400 rounded-full animate-pulse'></span>
                    搜索记录
                  </span>
                  <span className='text-xs font-bold text-violet-600 dark:text-cyan-400'>
                    {state.collected_data_summary.length} / {state.max_results}
                  </span>
                </div>
                <div className='w-full bg-gray-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden mb-2 shrink-0'>
                  <div
                    className='bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 dark:from-cyan-500 dark:to-blue-500 h-full transition-all duration-500 ease-out'
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
                {/* 搜索结果列表 */}
                <div className='flex-1 overflow-y-auto space-y-1.5 pr-1'>
                  {state.collected_data_summary.map((item, i) => (
                    <a
                      key={i}
                      href={item.url}
                      target='_blank'
                      rel='noopener noreferrer'
                      className='block bg-gray-50 dark:bg-black/40 rounded p-2 border border-gray-100 dark:border-slate-800 hover:border-violet-300 dark:hover:border-cyan-700 hover:bg-violet-50/50 dark:hover:bg-transparent transition-colors group'
                    >
                      <div className='text-violet-600 dark:text-cyan-400 group-hover:text-violet-700 dark:group-hover:text-cyan-300 text-xs font-medium line-clamp-1'>
                        {item.title}
                      </div>
                      <div className='text-[10px] text-gray-400 dark:text-slate-600 mt-0.5'>
                        {item.source}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}

          {/* System Logs - 限制最大高度 */}
          <div className='bg-white dark:bg-black/80 border border-gray-200 dark:border-slate-800 rounded-xl p-3 font-mono text-xs flex flex-col shrink-0 max-h-[150px] shadow-sm dark:shadow-none'>
            <h2 className='text-gray-500 dark:text-slate-400 mb-2 pb-1.5 border-b border-gray-100 dark:border-slate-800 flex justify-between shrink-0 text-xs'>
              <span>系统日志</span>
              {running && (
                <span className='text-violet-500 dark:text-cyan-500 animate-pulse'>
                  ● LIVE
                </span>
              )}
            </h2>
            <div className='flex-1 overflow-y-auto space-y-0.5 pr-1'>
              {state.logs.length === 0 && (
                <span className='text-gray-400 dark:text-slate-700 italic text-xs'>
                  等待开始...
                </span>
              )}
              {state.logs.slice(-15).map((log, i) => (
                <div
                  key={i}
                  className='text-gray-600 dark:text-slate-400 break-words leading-relaxed text-xs'
                >
                  <span className='text-violet-500 dark:text-cyan-700 mr-1'>
                    ›
                  </span>
                  {log}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>

        {/* Right Column: 主内容区域 */}
        <div className='lg:col-span-9 bg-white dark:bg-slate-900 border border-violet-100 dark:border-slate-800 rounded-xl overflow-hidden relative flex flex-col min-h-0 shadow-sm dark:shadow-none'>
          <div className='absolute inset-0 bg-[linear-gradient(rgba(139,92,246,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(139,92,246,0.02)_1px,transparent_1px)] dark:bg-[linear-gradient(rgba(6,182,212,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(6,182,212,0.03)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none'></div>

          {/* Tab 栏 */}
          {hasContent && (
            <div className='p-2 border-b border-gray-100 dark:border-slate-800 bg-gray-50/80 dark:bg-slate-950/50 backdrop-blur flex items-center gap-1 z-10 shrink-0'>
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => tab.available && setActiveTab(tab.id)}
                  disabled={!tab.available}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                    activeTab === tab.id
                      ? 'bg-violet-100 dark:bg-cyan-500/20 text-violet-700 dark:text-cyan-400 border border-violet-200 dark:border-cyan-500/50 shadow-sm'
                      : tab.available
                      ? 'text-gray-600 dark:text-slate-400 hover:text-gray-800 dark:hover:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-800/50'
                      : 'text-gray-300 dark:text-slate-600 cursor-not-allowed'
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              ))}
              {state.keyword && (
                <span className='ml-auto text-violet-600 dark:text-cyan-500 px-2 py-0.5 bg-violet-50 dark:bg-cyan-950/50 rounded text-xs border border-violet-100 dark:border-cyan-900'>
                  {state.keyword}
                </span>
              )}
            </div>
          )}

          {/* 主内容区域 */}
          <div className='flex-1 overflow-hidden relative z-0'>
            {/* Tab: 浏览器预览 (VNC) */}
            {activeTab === 'browser' && hasContent && (
              <VncViewer
                className='w-full h-full'
                pollingInterval={10000}
                active={isCollectingPhase}
                sandboxes={state.sandboxes || []}
                activeSandboxId={selectedSandboxId || state.active_sandbox_id}
                onSandboxSelect={handleSandboxSelect}
              />
            )}

            {/* Tab: 分析与撰写 */}
            {activeTab === 'analysis' && (
              <div className='h-full overflow-y-auto p-4'>
                {/* 分析摘要 */}
                {state.analysis && (
                  <div className='mb-4 bg-gray-50 dark:bg-slate-800/50 rounded-xl p-4 border border-gray-100 dark:border-slate-700'>
                    <h3 className='text-sm font-semibold text-violet-600 dark:text-cyan-400 mb-3'>
                      📊 分析结果
                    </h3>
                    <div className='grid grid-cols-3 gap-3 mb-3'>
                      <div className='text-center p-2 bg-emerald-50 dark:bg-green-900/20 rounded-lg border border-emerald-100 dark:border-green-800/30'>
                        <div className='text-xl font-bold text-emerald-600 dark:text-green-400'>
                          {state.analysis.sentiment_distribution?.['正面'] || 0}
                          %
                        </div>
                        <div className='text-xs text-slate-500 dark:text-slate-400'>
                          正面
                        </div>
                      </div>
                      <div className='text-center p-2 bg-amber-50 dark:bg-yellow-900/20 rounded-lg border border-amber-100 dark:border-yellow-800/30'>
                        <div className='text-xl font-bold text-amber-600 dark:text-yellow-400'>
                          {state.analysis.sentiment_distribution?.['中性'] || 0}
                          %
                        </div>
                        <div className='text-xs text-slate-500 dark:text-slate-400'>
                          中性
                        </div>
                      </div>
                      <div className='text-center p-2 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-800/30'>
                        <div className='text-xl font-bold text-red-500 dark:text-red-400'>
                          {state.analysis.sentiment_distribution?.['负面'] || 0}
                          %
                        </div>
                        <div className='text-xs text-slate-500 dark:text-slate-400'>
                          负面
                        </div>
                      </div>
                    </div>
                    {state.analysis.keywords &&
                      state.analysis.keywords.length > 0 && (
                        <div className='flex flex-wrap gap-1.5 mb-3'>
                          {state.analysis.keywords.map((kw, i) => (
                            <span
                              key={i}
                              className='px-2 py-0.5 bg-violet-50 dark:bg-cyan-900/30 text-violet-600 dark:text-cyan-300 text-xs rounded-full border border-violet-100 dark:border-cyan-800/50'
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}
                    {state.analysis.summary && (
                      <p className='text-sm text-gray-600 dark:text-slate-300 leading-relaxed mb-3'>
                        {state.analysis.summary}
                      </p>
                    )}
                    {/* 风险评估 */}
                    {state.analysis.risk_assessment && (
                      <div className='mt-3 pt-3 border-t border-gray-200 dark:border-slate-700'>
                        <h4 className='text-xs font-semibold text-gray-500 dark:text-slate-400 mb-2'>
                          风险评估
                        </h4>
                        <div className='flex gap-4 text-xs'>
                          <span className='text-gray-600 dark:text-slate-300'>
                            传播风险:{' '}
                            <span
                              className={
                                state.analysis.risk_assessment.spread_risk ===
                                '高'
                                  ? 'text-red-500 dark:text-red-400'
                                  : 'text-orange-500 dark:text-yellow-400'
                              }
                            >
                              {state.analysis.risk_assessment.spread_risk ||
                                '中'}
                            </span>
                          </span>
                          <span className='text-gray-600 dark:text-slate-300'>
                            声誉风险:{' '}
                            <span
                              className={
                                state.analysis.risk_assessment
                                  .reputation_risk === '高'
                                  ? 'text-red-500 dark:text-red-400'
                                  : 'text-orange-500 dark:text-yellow-400'
                              }
                            >
                              {state.analysis.risk_assessment.reputation_risk ||
                                '中'}
                            </span>
                          </span>
                          <span className='text-gray-600 dark:text-slate-300'>
                            趋势:{' '}
                            <span className='text-violet-600 dark:text-cyan-400'>
                              {state.analysis.risk_assessment.trend || '平稳'}
                            </span>
                          </span>
                        </div>
                      </div>
                    )}
                    {/* 关键观点 */}
                    {state.analysis.key_opinions &&
                      state.analysis.key_opinions.length > 0 && (
                        <div className='mt-3 pt-3 border-t border-gray-200 dark:border-slate-700'>
                          <h4 className='text-xs font-semibold text-gray-500 dark:text-slate-400 mb-2'>
                            关键观点
                          </h4>
                          <div className='space-y-2'>
                            {state.analysis.key_opinions
                              .slice(0, 3)
                              .map((op, i) => (
                                <div
                                  key={i}
                                  className='text-xs bg-white dark:bg-slate-900/50 rounded p-2 border border-gray-100 dark:border-transparent'
                                >
                                  <span
                                    className={`inline-block px-1.5 py-0.5 rounded text-[10px] mr-2 ${
                                      op.sentiment === '正面'
                                        ? 'bg-emerald-50 dark:bg-green-900/50 text-emerald-600 dark:text-green-400'
                                        : op.sentiment === '负面'
                                        ? 'bg-red-50 dark:bg-red-900/50 text-red-500 dark:text-red-400'
                                        : 'bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400'
                                    }`}
                                  >
                                    {op.sentiment}
                                  </span>
                                  <span className='text-gray-700 dark:text-slate-300'>
                                    {op.viewpoint}
                                  </span>
                                  <span className='text-gray-400 dark:text-slate-500 ml-2'>
                                    [{op.source}]
                                  </span>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
                  </div>
                )}

                {/* 报告内容（流式显示） */}
                {state.report_text && (
                  <div className='bg-gray-50 dark:bg-slate-800/30 rounded-xl p-4 border border-gray-100 dark:border-slate-700'>
                    <h3 className='text-sm font-semibold text-violet-600 dark:text-cyan-400 mb-3 flex items-center gap-2'>
                      📝 报告内容
                      {(state.status === 'writing' ||
                        state.status === 'rendering') && (
                        <span className='text-xs text-gray-400 dark:text-slate-500 animate-pulse'>
                          撰写中...
                        </span>
                      )}
                    </h3>
                    <div className='prose prose-gray dark:prose-invert prose-sm max-w-none'>
                      <pre className='whitespace-pre-wrap text-sm text-gray-600 dark:text-slate-300 leading-relaxed font-sans bg-transparent p-0 m-0'>
                        {state.report_text}
                      </pre>
                    </div>
                  </div>
                )}

                {/* 加载指示器 */}
                {!state.analysis && !state.report_text && (
                  <div className='flex flex-col items-center justify-center h-full gap-4'>
                    <div className='w-12 h-12 border-4 border-violet-500 dark:border-cyan-500 border-t-transparent rounded-full animate-spin'></div>
                    <p className='text-gray-500 dark:text-slate-400'>
                      {state.status === 'analyzing' ||
                      state.status === 'analyzed'
                        ? '正在分析数据...'
                        : '正在撰写报告...'}
                    </p>
                  </div>
                )}
                <div ref={analysisEndRef} />
              </div>
            )}

            {/* Tab: 最终报告 */}
            {activeTab === 'report' && state.final_html && (
              <div className='w-full h-full bg-white'>
                <iframe
                  srcDoc={state.final_html}
                  className='w-full h-full border-0'
                  title='Analysis Report'
                />
              </div>
            )}

            {/* 空闲状态 */}
            {state.status === 'idle' && (
              <div className='h-full flex flex-col items-center justify-center text-gray-400 dark:text-slate-400 gap-6 p-8'>
                <div className='w-20 h-20 relative'>
                  <div className='absolute inset-0 border-4 border-violet-200 dark:border-slate-800 rounded-full'></div>
                  <div className='absolute inset-0 flex items-center justify-center'>
                    <svg
                      className='w-10 h-10 text-violet-300 dark:text-slate-700'
                      fill='none'
                      stroke='currentColor'
                      viewBox='0 0 24 24'
                    >
                      <path
                        strokeLinecap='round'
                        strokeLinejoin='round'
                        strokeWidth={1.5}
                        d='M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z'
                      />
                    </svg>
                  </div>
                </div>
                <div className='text-center'>
                  <p className='text-lg font-semibold text-gray-700 dark:text-white mb-2'>
                    开始舆情分析
                  </p>
                  <p className='text-sm text-gray-400 dark:text-slate-500 max-w-md'>
                    在左侧输入关键词，点击&ldquo;开始分析&rdquo;按钮
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
