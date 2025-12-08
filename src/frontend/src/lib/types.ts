export type SearchResult = {
  title: string;
  url: string;
  snippet: string;
  source: string;
  date: string;
  platform?: string;
};

export type KeyOpinion = {
  viewpoint: string;
  source: string;
  sentiment: string;
};

export type RiskAssessment = {
  spread_risk?: string;
  reputation_risk?: string;
  trend?: string;
};

export type AnalysisResult = {
  keywords: string[];
  sentiment_score: number;
  sentiment_distribution: Record<string, number>;
  heat_trend: number[];
  summary: string;
  key_opinions?: KeyOpinion[];
  risk_assessment?: RiskAssessment;
};

export type SandboxInfo = {
  sandbox_id: string;
  vnc_url: string;
  livestream_url: string;
  active: boolean;
  created_at?: string;
};

export type AgentState = {
  keyword: string;
  status: "idle" | "collecting" | "collected" | "analyzing" | "analyzed" | "writing" | "written" | "rendering" | "complete" | "error";
  logs: string[];
  max_results: number;
  raw_data: SearchResult[];
  collected_data_summary: Array<{ title: string; url: string; source: string }>;
  analysis: AnalysisResult | null;
  report_text: string;
  final_html: string;
  collection_progress?: number;
  current_phase?: string;
  sandboxes?: SandboxInfo[];
  active_sandbox_id?: string;
};
