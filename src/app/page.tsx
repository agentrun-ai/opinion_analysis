'use client';

import { OpinionDashboard } from '@/components/OpinionDashboard';
import { CopilotKitCSSProperties, CopilotSidebar } from '@copilotkit/react-ui';
import { useState } from 'react';
import '@copilotkit/react-ui/styles.css';

export default function CopilotKitPage() {
  // Dark theme color for the sidebar to match our dashboard
  const themeColor = '#0f172a'; // slate-900

  return (
    <main
      style={
        { '--copilot-kit-primary-color': '#06b6d4' } as CopilotKitCSSProperties
      }
      className='bg-slate-950'
    >
      <CopilotSidebar
        disableSystemMessage={true}
        clickOutsideToClose={false}
        defaultOpen={true}
        labels={{
          title: '舆情分析',
          initial: '通过会话开始进行舆情分析',
        }}
        suggestions={[
          {
            title: '分析产品',
            message: "分析'新能源汽车'的舆情",
          },
          {
            title: '分析技术',
            message: "分析'人工智能大模型'的舆情",
          },
          {
            title: '分析行业',
            message: "分析'电商直播'的舆情",
          },
        ]}
      >
        <OpinionDashboard />
      </CopilotSidebar>
    </main>
  );
}
