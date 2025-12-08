'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { HttpAgent, AgentSubscriber } from '@ag-ui/client';
import type {
  StateSnapshotEvent,
  StateDeltaEvent,
  RunErrorEvent,
  Message,
} from '@ag-ui/client';
import { ENDPOINT } from '@/lib/const';

/**
 * 使用 AG-UI 协议的 Agent 状态 Hook
 *
 * 直接使用 AG-UI 的 STATE_SNAPSHOT 事件进行状态同步
 */

function randomUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

interface UseAgentStateOptions<T> {
  name: string;
  initialState: T;
  agentUrl?: string;
}

interface UseAgentStateResult<T> {
  state: T;
  setState: (newState: T | ((prev: T) => T)) => void;
  running: boolean;
  sendMessage: (message: string) => Promise<void>;
  messages: Message[];
  error: string | null;
  runId: string | null;
}

export function useAgentState<T extends Record<string, unknown>>(
  options: UseAgentStateOptions<T>
): UseAgentStateResult<T> {
  const { name, initialState, agentUrl = `${ENDPOINT}/api/agent` } = options;

  const [state, setStateInternal] = useState<T>(initialState);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [runId, setRunId] = useState<string | null>(null);

  const stateRef = useRef<T>(initialState);
  const isUnmountedRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 保持 stateRef 同步
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  // 组件卸载时清理
  useEffect(() => {
    isUnmountedRef.current = false;

    return () => {
      isUnmountedRef.current = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // 更新状态
  const setState = useCallback((newState: T | ((prev: T) => T)) => {
    if (isUnmountedRef.current) return;

    setStateInternal((prev) => {
      const updated =
        typeof newState === 'function' ? newState(prev) : newState;
      return updated;
    });
  }, []);

  // 发送消息到 Agent
  const sendMessage = useCallback(
    async (message: string) => {
      if (running) {
        console.log('⏳ 上一个请求仍在进行中...');
        return;
      }

      setRunning(true);
      setError(null);

      // 创建新的 AbortController
      abortControllerRef.current = new AbortController();

      // 创建新的 Agent 实例
      const agent = new HttpAgent({
        url: agentUrl,
        agentId: name,
        initialState: stateRef.current as Record<string, unknown>,
        debug: true,
      });

      // 添加用户消息
      const userMessage: Message = {
        id: randomUUID(),
        role: 'user',
        content: message,
      };
      agent.addMessage(userMessage);

      if (!isUnmountedRef.current) {
        setMessages((prev) => [...prev, userMessage]);
      }

      const subscriber: AgentSubscriber = {
        onRunStartedEvent: ({ event }) => {
          if (isUnmountedRef.current) return;
          console.log('🚀 Run started:', event.runId);
          setRunId(event.runId);
        },
        onStateSnapshotEvent: ({ event }: { event: StateSnapshotEvent }) => {
          if (isUnmountedRef.current) return;
          console.log('📸 STATE_SNAPSHOT 收到:', event.snapshot);
          const snapshot = event.snapshot as T;
          if (snapshot) {
            setStateInternal(snapshot);
          }
        },
        onStateDeltaEvent: ({ event }: { event: StateDeltaEvent }) => {
          if (isUnmountedRef.current) return;
          console.log('📝 State delta:', event.delta);
          setStateInternal((prev) => ({
            ...prev,
            ...(event.delta as unknown as Partial<T>),
          }));
        },
        onTextMessageContentEvent: ({ textMessageBuffer }) => {
          console.log('💬 Agent message:', textMessageBuffer);
        },
        onTextMessageEndEvent: ({ textMessageBuffer }) => {
          if (isUnmountedRef.current) return;
          const agentMessage: Message = {
            id: randomUUID(),
            role: 'assistant',
            content: textMessageBuffer,
          };
          setMessages((prev) => [...prev, agentMessage]);
        },
        onRunErrorEvent: ({ event }: { event: RunErrorEvent }) => {
          if (isUnmountedRef.current) return;
          console.error('❌ Run error:', event.message);
          setError(event.message || '运行错误');
        },
        onRunFinishedEvent: () => {
          if (isUnmountedRef.current) return;
          console.log('✅ Run finished');
          setRunning(false);
        },
      };

      try {
        await agent.runAgent(
          { abortController: abortControllerRef.current },
          subscriber
        );
      } catch (err: unknown) {
        if (isUnmountedRef.current) return;

        const error = err as Error;
        if (error.name === 'AbortError') {
          console.log('🛑 Request aborted');
        } else {
          setError(error.message || '未知错误');
          console.error('Agent error:', err);
        }
      } finally {
        if (!isUnmountedRef.current) {
          setRunning(false);
        }
        abortControllerRef.current = null;
      }
    },
    [agentUrl, name, running]
  );

  return {
    state,
    setState,
    running,
    sendMessage,
    messages,
    error,
    runId,
  };
}
