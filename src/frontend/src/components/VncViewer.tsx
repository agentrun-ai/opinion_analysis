'use client';

import { ENDPOINT } from '@/lib/const';
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { SandboxInfo } from '@/lib/types';

interface VncViewerProps {
  className?: string;
  pollingInterval?: number;
  active?: boolean;
  // 支持多 sandbox 切换
  sandboxes?: SandboxInfo[];
  activeSandboxId?: string;
  onSandboxSelect?: (sandboxId: string) => void;
}

interface VncState {
  available: boolean;
  vnc_url: string | null;
  livestream_url: string | null;
  sandbox_id: string | null;
  message: string;
}

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// 全局变量存储 RFB 类（避免重复加载）
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let cachedRFB: any = null;
let loadingPromise: Promise<void> | null = null;

export function VncViewer({
  className = '',
  pollingInterval = 10000,
  active = true,
  sandboxes = [],
  activeSandboxId,
  onSandboxSelect,
}: VncViewerProps) {
  const screenRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rfbRef = useRef<any>(null);
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);
  const [currentSandboxId, setCurrentSandboxId] = useState<string | null>(null);
  const [rfbLoaded, setRfbLoaded] = useState(!!cachedRFB);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastUrlRef = useRef<string | null>(null);
  const lastActiveSandboxIdRef = useRef<string | null>(null);
  
  // 重连间隔（毫秒）
  const RECONNECT_INTERVAL = 10000;
  
  // 是否显示 sandbox 选择器
  const [showSandboxSelector, setShowSandboxSelector] = useState(false);
  
  // 使用 useMemo 稳定 sandboxes，避免引用变化导致重复渲染
  const sandboxIds = sandboxes.map(s => s.sandbox_id).join(',');
  const stableSandboxes = useMemo(() => {
    return sandboxes.map(s => ({
      sandbox_id: s.sandbox_id,
      vnc_url: s.vnc_url,
      livestream_url: s.livestream_url,
      active: s.active,
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sandboxIds]);

  // 加载本地 noVNC RFB 模块
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (cachedRFB) {
      setRfbLoaded(true);
      return;
    }

    if (loadingPromise) {
      loadingPromise.then(() => {
        if (cachedRFB) setRfbLoaded(true);
      });
      return;
    }

    // 使用 ES module script 从本地 public 目录加载 noVNC
    loadingPromise = new Promise<void>((resolve) => {
      const script = document.createElement('script');
      script.type = 'module';
      script.textContent = `
        try {
          // 从 GitHub 版本的 noVNC 加载（使用 core 目录）
          const { default: RFB } = await import('/novnc/core/rfb.js');
          window.__noVNC_RFB = RFB;
          console.log('✅ noVNC RFB module loaded successfully');
          window.dispatchEvent(new CustomEvent('novnc-loaded', { detail: { success: true } }));
        } catch (err) {
          console.error('❌ Failed to load noVNC:', err);
          window.dispatchEvent(new CustomEvent('novnc-loaded', { detail: { success: false, error: err.message } }));
        }
      `;

      const handleLoaded = (e: Event) => {
        const customEvent = e as CustomEvent;
        if (customEvent.detail?.success) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          cachedRFB = (window as any).__noVNC_RFB;
          console.log('✅ noVNC RFB cached');
          setRfbLoaded(true);
        } else {
          console.error('❌ noVNC load failed:', customEvent.detail?.error);
          setError(`无法加载 VNC 组件: ${customEvent.detail?.error}`);
          setStatus('error');
        }
        window.removeEventListener('novnc-loaded', handleLoaded);
        resolve();
      };

      window.addEventListener('novnc-loaded', handleLoaded);
      document.head.appendChild(script);

      setTimeout(() => {
        if (!cachedRFB) {
          console.warn('⚠️ noVNC load timeout');
          setError('VNC 组件加载超时');
          setStatus('error');
          resolve();
        }
      }, 10000);
    });
  }, []);

  // 根据当前页面协议调整 WebSocket URL
  // 如果页面是 http，则使用 ws；如果是 https，则使用 wss
  const adjustWebSocketUrl = useCallback((url: string): string => {
    if (typeof window === 'undefined') return url;
    
    const isHttps = window.location.protocol === 'https:';
    
    // 如果页面是 http，确保 WebSocket 使用 ws
    if (!isHttps && url.startsWith('wss://')) {
      const adjustedUrl = url.replace('wss://', 'ws://');
      console.log('🔄 Adjusting WebSocket URL for HTTP page: wss -> ws');
      return adjustedUrl;
    }
    
    // 如果页面是 https，确保 WebSocket 使用 wss
    if (isHttps && url.startsWith('ws://')) {
      const adjustedUrl = url.replace('ws://', 'wss://');
      console.log('🔄 Adjusting WebSocket URL for HTTPS page: ws -> wss');
      return adjustedUrl;
    }
    
    return url;
  }, []);

  // 清理 RFB 连接
  const cleanupRfb = useCallback(() => {
    if (rfbRef.current) {
      try {
        rfbRef.current.disconnect();
        console.log('🔌 VNC disconnected (cleanup)');
      } catch (e) {
        console.warn('RFB disconnect error:', e);
      }
      rfbRef.current = null;
    }
  }, []);

  // 连接到 VNC
  const connectVnc = useCallback(
    (url: string) => {
      if (!screenRef.current) {
        console.error('Screen ref not available');
        return;
      }

      if (!cachedRFB) {
        console.error('RFB not loaded');
        return;
      }

      // 如果已经连接到同一个 URL，不重复连接
      if (rfbRef.current && lastUrlRef.current === url) {
        console.log('Already connected to this URL, skipping');
        return;
      }

      // 清理旧连接
      cleanupRfb();

      setStatus('connecting');
      setError(null);

      try {
        console.log(
          '🔗 Creating RFB connection to:',
          url.substring(0, 100) + '...'
        );
        console.log('📦 Screen element:', screenRef.current);

        // 创建 RFB 实例
        // 根据 noVNC API 文档，直接传入 WebSocket URL
        const rfb = new cachedRFB(screenRef.current, url, {
          shared: true,
          credentials: { password: '' },
        });

        // 配置 RFB
        rfb.viewOnly = true;
        rfb.scaleViewport = true;
        rfb.resizeSession = false;
        rfb.showDotCursor = false;
        rfb.background = 'rgb(0, 0, 0)';

        // 事件处理
        rfb.addEventListener('connect', () => {
          console.log('✅ VNC connected!');
          setStatus('connected');
          setError(null);
          lastUrlRef.current = url;
        });

        rfb.addEventListener(
          'disconnect',
          (e: CustomEvent<{ clean: boolean }>) => {
            console.log('🔌 VNC disconnected:', e.detail);
            if (e.detail?.clean) {
              setStatus('disconnected');
              setError(null);
            } else {
              setStatus('error');
              setError('连接断开（非正常）');
            }
            lastUrlRef.current = null;
          }
        );

        rfb.addEventListener(
          'securityfailure',
          (e: CustomEvent<{ status: number; reason: string }>) => {
            console.error('🔒 VNC security failure:', e.detail);
            setStatus('error');
            setError(`安全验证失败: ${e.detail?.reason || '未知原因'}`);
          }
        );

        rfb.addEventListener(
          'credentialsrequired',
          (e: CustomEvent<{ types: string[] }>) => {
            console.log('🔑 VNC credentials required:', e.detail?.types);
            // 对于 agentrun 的 livestream，不需要密码
            rfb.sendCredentials({ password: '' });
          }
        );

        rfb.addEventListener(
          'desktopname',
          (e: CustomEvent<{ name: string }>) => {
            console.log('🖥️ VNC desktop name:', e.detail?.name);
          }
        );

        rfbRef.current = rfb;
      } catch (err) {
        console.error('❌ VNC connection error:', err);
        setStatus('error');
        setError(err instanceof Error ? err.message : '连接失败');
      }
    },
    [cleanupRfb]
  );

  // 获取 VNC URL
  // 注意：此函数使用 ref 来读取当前 status，避免依赖 status 导致的重复渲染
  const statusRef = useRef<ConnectionStatus>(status);
  statusRef.current = status;
  
  const fetchVncUrl = useCallback(async (forceReconnect = false) => {
    if (!rfbLoaded) {
      console.log('⏳ RFB not loaded yet, skipping fetch');
      return;
    }
    
    // 使用 ref 读取当前状态，避免依赖 status
    const currentStatus = statusRef.current;

    try {
      // 如果有传入的 sandboxes 和 activeSandboxId，优先使用
      if (stableSandboxes.length > 0 && activeSandboxId) {
        const targetSandbox = sandboxes.find(s => s.sandbox_id === activeSandboxId);
        if (targetSandbox && targetSandbox.livestream_url) {
          console.log('🔍 Using sandbox from props:', activeSandboxId.slice(0, 8));
          setCurrentSandboxId(targetSandbox.sandbox_id);
          
          // 只有在强制重连、URL 变化、或未连接状态下才重连
          // 关键修复：不要在 connected 状态下因为轮询而重连
          const needReconnect =
            forceReconnect ||
            targetSandbox.livestream_url !== lastUrlRef.current ||
            currentStatus === 'disconnected' ||
            currentStatus === 'error';

          if (needReconnect && currentStatus !== 'connected') {
            console.log('🔄 URL changed or need reconnect, connecting...');
            const adjustedUrl = adjustWebSocketUrl(targetSandbox.livestream_url);
            connectVnc(adjustedUrl);
          } else if (forceReconnect) {
            // 强制重连时，即使已连接也重连
            console.log('🔄 Force reconnect requested...');
            const adjustedUrl = adjustWebSocketUrl(targetSandbox.livestream_url);
            connectVnc(adjustedUrl);
          }
          return;
        }
      }

      console.log('🔍 Fetching VNC URL from API...');
      const response = await fetch(`${ENDPOINT}/api/browser/vnc`);
      const data: VncState = await response.json();
      console.log('📡 VNC API response:', data);

      if (data.available && data.livestream_url) {
        setCurrentSandboxId(data.sandbox_id);

        // 检查 URL 是否变化或需要重连
        // 关键修复：不要在 connected 状态下因为轮询而重连
        const needReconnect =
          forceReconnect ||
          data.livestream_url !== lastUrlRef.current ||
          currentStatus === 'disconnected' ||
          currentStatus === 'error';

        if (needReconnect && currentStatus !== 'connected') {
          console.log('🔄 URL changed or need reconnect, connecting...');
          const adjustedUrl = adjustWebSocketUrl(data.livestream_url);
          connectVnc(adjustedUrl);
        } else if (forceReconnect) {
          // 强制重连时，即使已连接也重连
          console.log('🔄 Force reconnect requested...');
          const adjustedUrl = adjustWebSocketUrl(data.livestream_url);
          connectVnc(adjustedUrl);
        } else {
          console.log('✓ Already connected to same URL');
        }
      } else {
        console.log('⚠️ VNC not available:', data.message);
        setError(data.message || 'VNC 不可用');
        setStatus('disconnected');
      }
    } catch (err) {
      console.error('❌ Failed to fetch VNC URL:', err);
      setError('无法获取 VNC URL');
      setStatus('error');
    }
  }, [connectVnc, adjustWebSocketUrl, rfbLoaded, stableSandboxes, sandboxes, activeSandboxId]);

  // 轮询 URL - 使用稳定的依赖
  useEffect(() => {
    if (!active || !rfbLoaded) {
      cleanupRfb();
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      if (!active) {
        setStatus('disconnected');
        lastUrlRef.current = null;
      }
      return;
    }

    // 立即获取一次
    fetchVncUrl();

    // 开始轮询（使用较长间隔避免频繁刷新）
    pollingRef.current = setInterval(() => fetchVncUrl(), pollingInterval);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, pollingInterval, rfbLoaded]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      cleanupRfb();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [cleanupRfb]);
  
  // 连接失败时自动重连（每 10 秒尝试一次）
  useEffect(() => {
    // 清除之前的重连定时器
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    
    // 如果处于错误状态且组件处于激活状态，设置自动重连
    if (status === 'error' && active && rfbLoaded) {
      console.log(`🔄 将在 ${RECONNECT_INTERVAL / 1000} 秒后自动重连...`);
      reconnectTimerRef.current = setTimeout(() => {
        console.log('🔄 自动重连中...');
        cleanupRfb();
        lastUrlRef.current = null;
        fetchVncUrl(true);
      }, RECONNECT_INTERVAL);
    }
    
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, active, rfbLoaded]);

  // 手动重连
  const handleReconnect = () => {
    cleanupRfb();
    lastUrlRef.current = null;
    fetchVncUrl();
  };

  // 处理 sandbox 切换
  const handleSandboxClick = (selectedId: string) => {
    if (onSandboxSelect) {
      onSandboxSelect(selectedId);
    }
    setShowSandboxSelector(false);
  };

  // 当 activeSandboxId 变化时，触发重连
  useEffect(() => {
    // 只有当 activeSandboxId 真正变化时才重连
    if (
      activeSandboxId && 
      activeSandboxId !== lastActiveSandboxIdRef.current && 
      rfbLoaded
    ) {
      console.log('🔄 Active sandbox changed:', lastActiveSandboxIdRef.current, '->', activeSandboxId);
      lastActiveSandboxIdRef.current = activeSandboxId;
      
      // 清理旧连接并强制重连
      cleanupRfb();
      lastUrlRef.current = null;
      
      // 延迟一点以确保状态更新
      setTimeout(() => {
        fetchVncUrl(true);
      }, 100);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSandboxId, rfbLoaded]);

  return (
    <div className={`relative bg-black ${className}`}>
      {/* 状态栏 */}
      <div className='absolute top-0 left-0 right-0 bg-slate-950/95 backdrop-blur-sm px-3 py-2 z-10 flex items-center justify-between border-b border-cyan-900/50'>
        <div className='flex items-center gap-2'>
          <span
            className={`w-2 h-2 rounded-full ${
              status === 'connected'
                ? 'bg-green-500'
                : status === 'connecting'
                ? 'bg-yellow-500 animate-pulse'
                : status === 'error'
                ? 'bg-red-500'
                : 'bg-slate-500'
            }`}
          ></span>
          <span className='text-xs text-cyan-400'>
            {!rfbLoaded && '⏳ 加载 VNC 组件...'}
            {rfbLoaded && status === 'connected' && '🖥️ VNC 已连接'}
            {rfbLoaded && status === 'connecting' && '⏳ 连接中...'}
            {rfbLoaded && status === 'error' && `❌ ${error || '连接错误'}`}
            {rfbLoaded && status === 'disconnected' && '⚪ 等待连接...'}
          </span>
        </div>
        <div className='flex items-center gap-3'>
          <button
            onClick={handleReconnect}
            disabled={!rfbLoaded}
            className='text-xs text-cyan-400 hover:text-cyan-300 transition-colors p-1 disabled:opacity-50'
            title='重新连接'
          >
            🔄
          </button>
          
          {/* Sandbox ID - 可点击切换 */}
          {currentSandboxId && (
            <div className='relative'>
              <button
                onClick={() => setShowSandboxSelector(!showSandboxSelector)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  stableSandboxes.length > 1
                    ? 'text-cyan-400 hover:text-cyan-300 hover:bg-cyan-900/30 cursor-pointer'
                    : 'text-slate-600 cursor-default'
                }`}
                title={stableSandboxes.length > 1 ? '点击切换 Sandbox' : 'Sandbox ID'}
              >
                {currentSandboxId.slice(0, 8)}...
                {stableSandboxes.length > 1 && (
                  <span className='ml-1 text-cyan-500'>▼</span>
                )}
              </button>
              
              {/* Sandbox 选择器下拉菜单 */}
              {showSandboxSelector && stableSandboxes.length > 1 && (
                <div className='absolute top-full right-0 mt-1 bg-slate-900 border border-cyan-800/50 rounded-lg shadow-xl z-20 min-w-[200px] overflow-hidden'>
                  <div className='px-3 py-2 text-xs text-slate-400 border-b border-slate-800'>
                    选择 Sandbox ({stableSandboxes.length} 个可用)
                  </div>
                  {stableSandboxes.map((sb) => (
                    <button
                      key={sb.sandbox_id}
                      onClick={() => handleSandboxClick(sb.sandbox_id)}
                      className={`w-full px-3 py-2 text-left text-xs transition-colors flex items-center gap-2 ${
                        sb.sandbox_id === (activeSandboxId || currentSandboxId)
                          ? 'bg-cyan-900/30 text-cyan-400'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <span
                        className={`w-2 h-2 rounded-full ${
                          sb.active ? 'bg-green-500' : 'bg-slate-500'
                        }`}
                      ></span>
                      <span className='font-mono'>{sb.sandbox_id.slice(0, 12)}...</span>
                      {sb.sandbox_id === (activeSandboxId || currentSandboxId) && (
                        <span className='ml-auto text-cyan-500'>✓</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* 点击其他地方关闭选择器 */}
      {showSandboxSelector && (
        <div
          className='fixed inset-0 z-10'
          onClick={() => setShowSandboxSelector(false)}
        />
      )}

      {/* VNC 显示区域 */}
      <div
        ref={screenRef}
        className='w-full h-full pt-9 overflow-hidden'
        style={{
          minHeight: '400px',
          backgroundColor: '#000',
        }}
      >
        {status !== 'connected' && (
          <div className='absolute inset-0 pt-9 flex flex-col items-center justify-center gap-4'>
            {!rfbLoaded && (
              <>
                <div className='w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin'></div>
                <span className='text-cyan-400 text-sm'>加载 VNC 组件...</span>
              </>
            )}
            {rfbLoaded && status === 'connecting' && (
              <>
                <div className='w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin'></div>
                <span className='text-cyan-400 text-sm'>
                  正在连接浏览器预览...
                </span>
              </>
            )}
            {rfbLoaded && status === 'error' && (
              <>
                <div className='text-4xl'>❌</div>
                <span className='text-red-400 text-sm text-center px-4'>
                  {error}
                </span>
                <span className='text-slate-500 text-xs'>
                  将在 {RECONNECT_INTERVAL / 1000} 秒后自动重连
                </span>
                <button
                  onClick={handleReconnect}
                  className='px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-sm rounded-lg transition-colors'
                >
                  立即重试
                </button>
              </>
            )}
            {rfbLoaded && status === 'disconnected' && (
              <>
                <div className='w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center'>
                  <svg
                    className='w-8 h-8 text-slate-600'
                    fill='none'
                    stroke='currentColor'
                    viewBox='0 0 24 24'
                  >
                    <path
                      strokeLinecap='round'
                      strokeLinejoin='round'
                      strokeWidth={1.5}
                      d='M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z'
                    />
                  </svg>
                </div>
                <span className='text-slate-500 text-sm'>
                  等待浏览器启动...
                </span>
              </>
            )}
          </div>
        )}
      </div>

      {active && status === 'connected' && (
        <div className='absolute bottom-2 right-2 text-xs text-slate-600 flex items-center gap-1'>
          <span className='w-1.5 h-1.5 bg-green-500 rounded-full'></span>
          实时预览
        </div>
      )}
    </div>
  );
}
