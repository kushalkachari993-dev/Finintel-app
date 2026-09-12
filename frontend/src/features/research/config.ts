import type { ModeCopy, WorkMode } from "./types";

export const EXAMPLES = [
  "What is ROE?",
  "Current price of HDFC Bank",
  "Compare HDFC Bank vs ICICI Bank",
  "Top undervalued IT stocks in India",
  "Latest news about Infosys",
  "Fundamental analysis of TCS",
];

export const REPORT_EXAMPLES = [
  "Generate a fundamental report on TCS",
  "Compare HDFC Bank and ICICI Bank as an investment report",
  "Create a report on undervalued IT stocks in India",
  "Prepare a news impact report for Infosys",
];

export const PROMPT_PRESENTATION: Record<
  WorkMode,
  Array<{ icon: string; label: string; detail: string }>
> = {
  chat: [
    { icon: "%", label: "Learn", detail: "Understand a financial metric" },
    { icon: "₹", label: "Quote", detail: "Check price and market context" },
    { icon: "↔", label: "Compare", detail: "Evaluate companies side by side" },
  ],
  report: [
    { icon: "▤", label: "Company", detail: "Build a structured company brief" },
    { icon: "↔", label: "Compare", detail: "Create an investment comparison" },
    { icon: "⌁", label: "Screen", detail: "Research a sector or market theme" },
  ],
};

export const MODE_COPY: Record<WorkMode, ModeCopy> = {
  chat: {
    eyebrow: "AI equity research, grounded with sources",
    title: "Research chat",
    welcome:
      "Ask about prices, ratios, company fundamentals, comparisons, discovery screens, or news context.",
    placeholder: "Ask about HDFC Bank, ROE, IT stocks, or latest market news",
    loading: "Routing, retrieving sources, and preparing a grounded answer.",
    submit: "Run research",
  },
  report: {
    eyebrow: "Structured research briefs with export",
    title: "Report generator",
    welcome:
      "Enter a company, comparison, sector, or market theme to generate a structured analyst-style report.",
    placeholder:
      "Enter companies or a theme, e.g. HDFC Bank vs ICICI Bank or undervalued IT stocks",
    loading: "Routing, retrieving sources, and assembling a structured report.",
    submit: "Generate report",
  },
};
