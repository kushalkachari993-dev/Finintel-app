import { PROMPT_PRESENTATION } from "../config";
import type { ModeCopy, WorkMode } from "../types";

function TrustStrip() {
  return (
    <div className="trust-strip" aria-label="Supported workflows">
      <span>Grounded sources</span>
      <span>Freshness labeled</span>
      <span>Comparison-ready</span>
      <span>Saved research</span>
    </div>
  );
}

type WelcomePanelProps = {
  examples: string[];
  modeCopy: ModeCopy;
  onSelectExample: (example: string) => void;
  workMode: WorkMode;
};

export function WelcomePanel({
  examples,
  modeCopy,
  onSelectExample,
  workMode,
}: WelcomePanelProps) {
  return (
    <section className="welcome-panel">
      <span className="welcome-kicker">Market research workspace</span>
      <h2>How can I help with Indian markets today?</h2>
      <p>{modeCopy.welcome}</p>
      <div
        className="welcome-query-grid"
        aria-label="Suggested research prompts"
        role="group"
      >
        {examples.slice(0, 3).map((example, index) => {
          const presentation = PROMPT_PRESENTATION[workMode][index];
          return (
            <button
              key={example}
              type="button"
              onClick={() => onSelectExample(example)}
              aria-label={`Use prompt: ${example}`}
            >
              <span className="prompt-card-heading">
                <span className="prompt-card-icon" aria-hidden="true">
                  {presentation.icon}
                </span>
                <span className="prompt-card-label">{presentation.label}</span>
              </span>
              <strong>{example}</strong>
              <small>{presentation.detail}</small>
              <span className="prompt-card-action" aria-hidden="true">
                Explore <span>→</span>
              </span>
            </button>
          );
        })}
      </div>
      <p className="welcome-query-hint">
        Swipe to explore more prompts <span aria-hidden="true">→</span>
      </p>
      <TrustStrip />
    </section>
  );
}
