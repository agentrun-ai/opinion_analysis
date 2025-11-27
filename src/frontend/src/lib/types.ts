export type SearchResult = {
  title: string;
  url: string;
  snippet: string;
  source: string;
  date: string;
};

export type AnalysisResult = {
  keywords: string[];
  sentiment_score: number;
  sentiment_distribution: Record<string, number>;
  heat_trend: number[];
  summary: string;
};

export type AgentState = {
  keyword: string;
  status: "idle" | "collecting" | "collected" | "analyzing" | "analyzed" | "writing" | "written" | "rendering" | "complete";
  logs: string[];
  max_results: number;
  batch_size: number;
  raw_data: SearchResult[];
  collected_data_summary: Array<{ title: string; url: string; source: string }>;
  batch_analyses: string[];
  analysis: AnalysisResult | null;
  report_text: string;
  final_html: string;
};
