"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui";
import { SkillCard, SkillDetail } from "@/components/skills";
import { useSkill, useSkills, useInstallAgentSkill } from "@/hooks";
import { useFleet } from "@/hooks";
import type { SkillRegistry, SkillSummary } from "@/lib/types";

const REGISTRY_LABELS: Record<SkillRegistry, string> = {
  clawrium: "Clawrium",
  openclaw: "OpenClaw",
  hermes: "Hermes",
  zeroclaw: "ZeroClaw",
};

export default function SkillsPage() {
  const { data: catalog, isLoading, error } = useSkills();
  const [activeRegistry, setActiveRegistry] = useState<SkillRegistry>(
    "clawrium",
  );
  const [selected, setSelected] = useState<SkillSummary | null>(null);

  const counts = useMemo(() => {
    if (!catalog) return {} as Record<SkillRegistry, number>;
    return Object.fromEntries(
      Object.entries(catalog.skills).map(([registry, list]) => [
        registry,
        list.length,
      ]),
    ) as Record<SkillRegistry, number>;
  }, [catalog]);

  const visibleSkills = catalog?.skills[activeRegistry] ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Skills"
        description="Browse and install skills onto your agents. Skills add capabilities like TDD workflows, code review, and more."
      />

      {error ? (
        <div
          role="alert"
          className="bg-surface rounded-xl border border-default p-6 text-sm text-status-warning"
        >
          Failed to load skills catalog:{" "}
          {error instanceof Error ? error.message : String(error)}
        </div>
      ) : null}

      {catalog?.error ? (
        <div
          role="alert"
          className="bg-surface rounded-xl border border-default p-4 text-sm text-status-warning"
        >
          Skills catalog is currently unavailable on the server (likely a
          filesystem permission issue). Showing empty tabs as a fallback —
          check the GUI server log for details.
        </div>
      ) : null}

      {isLoading ? (
        <div
          aria-live="polite"
          className="bg-surface rounded-xl border border-default p-8 text-center text-muted text-sm"
        >
          Loading skills catalog...
        </div>
      ) : catalog ? (
        <>
          {/* `role="group"` instead of `<nav>` because these buttons
              filter the page's already-loaded data, they do not
              navigate to new URLs. Using <nav> pollutes the landmark
              menu for AT users with what looks like a navigation
              region. APG's full Tabs Pattern (tablist + tabpanel +
              arrow-key roving tabindex) would also work, but is heavy
              for an in-page filter; `role="group"` carries the same
              semantic intent without the keyboard contract. */}
          <div
            role="group"
            aria-label="Skill registries"
            className="flex gap-1 border-b border-default"
          >
            {catalog.registries.map((registry) => {
              const isActive = registry === activeRegistry;
              const count = counts[registry] ?? 0;
              const label = REGISTRY_LABELS[registry] ?? registry;
              return (
                <button
                  key={registry}
                  type="button"
                  // `aria-current="true"` is the right WAI-ARIA token
                  // for "this filter is selected"; `"page"` is reserved
                  // for routing (selected nav item that matches the
                  // current URL).
                  aria-current={isActive ? "true" : undefined}
                  // Use a comma rather than an em-dash — most screen
                  // readers verbalize U+2014 as "em dash" instead of
                  // pausing, which mangles the spoken count phrasing.
                  aria-label={`${label}, ${count} skill${
                    count === 1 ? "" : "s"
                  }`}
                  onClick={() => setActiveRegistry(registry)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                    isActive
                      ? "border-primary text-primary"
                      : "border-transparent text-secondary hover:text-primary"
                  }`}
                >
                  {label}
                  <span aria-hidden="true" className="ml-2 text-xs text-muted">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {visibleSkills.length > 0 ? (
            <div className="space-y-3">
              {visibleSkills.map((skill) => (
                <SkillCard
                  key={skill.ref}
                  skill={skill}
                  onSelect={() => setSelected(skill)}
                />
              ))}
            </div>
          ) : (
            <EmptyState registry={activeRegistry} />
          )}
        </>
      ) : null}

      <SkillDetailModal
        skill={selected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function EmptyState({ registry }: { registry: SkillRegistry }) {
  return (
    <div className="bg-surface rounded-xl border border-default p-12 text-center space-y-2">
      <p className="text-sm text-primary-text font-medium">
        No skills registered under{" "}
        <code className="bg-panel text-secondary px-1 py-0.5 rounded">
          {registry}/
        </code>
      </p>
      <p className="text-xs text-muted">
        Add one under{" "}
        <code className="bg-panel text-secondary px-1 py-0.5 rounded">
          skills/{registry}/&lt;name&gt;/
        </code>{" "}
        in the clawrium repo.
      </p>
    </div>
  );
}

function SkillDetailModal({
  skill,
  onClose,
}: {
  skill: SkillSummary | null;
  onClose: () => void;
}) {
  const { data, isLoading, error } = useSkill(
    skill?.registry ?? null,
    skill?.name ?? null,
  );
  const { data: fleet } = useFleet();
  const installMutation = useInstallAgentSkill();
  const [targetAgent, setTargetAgent] = useState<string>("");
  const [installSuccess, setInstallSuccess] = useState<string | null>(null);

  const agents = fleet?.agents ?? [];

  const handleInstall = () => {
    if (!targetAgent || !skill) return;
    setInstallSuccess(null);
    installMutation.mutate(
      { agentKey: targetAgent, registry: skill.registry, name: skill.name },
      {
        onSuccess: () => {
          setInstallSuccess(
            `Installed ${skill.ref} on ${targetAgent}`,
          );
          setTargetAgent("");
        },
      },
    );
  };

  return (
    <Modal
      open={!!skill}
      onClose={() => {
        setInstallSuccess(null);
        setTargetAgent("");
        onClose();
      }}
      title={skill ? skill.ref : "Skill detail"}
    >
      {isLoading ? (
        <div
          aria-live="polite"
          className="text-sm text-muted py-6 text-center"
        >
          Loading...
        </div>
      ) : error ? (
        <div role="alert" className="text-sm text-status-warning py-6">
          Failed to load skill:{" "}
          {error instanceof Error ? error.message : String(error)}
        </div>
      ) : data ? (
        <>
          <SkillDetail skill={data} />

          {/* Install to Agent section */}
          <div className="mt-4 pt-4 border-t border-default">
            <h3 className="text-xs font-semibold text-primary-text mb-2">
              Install to Agent
            </h3>
            {agents.length === 0 ? (
              <p className="text-xs text-muted">
                No agents available. Create an agent first.
              </p>
            ) : (
              <div className="flex items-center gap-2">
                <select
                  value={targetAgent}
                  onChange={(e) => setTargetAgent(e.target.value)}
                  className="flex-1 text-sm border border-default rounded px-2 py-1.5 bg-surface text-primary-text"
                  aria-label="Select agent to install skill on"
                >
                  <option value="">Select an agent...</option>
                  {agents.map((agent) => (
                    <option key={agent.agent_key} value={agent.agent_key}>
                      {agent.agent_name} ({agent.agent_type})
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  disabled={
                    !targetAgent || installMutation.isPending
                  }
                  onClick={handleInstall}
                >
                  {installMutation.isPending ? "Installing..." : "Install"}
                </Button>
              </div>
            )}
            {installSuccess ? (
              <p className="mt-2 text-xs text-emerald-600">{installSuccess}</p>
            ) : null}
            {installMutation.isError ? (
              <p className="mt-2 text-xs text-status-warning">
                Install failed:{" "}
                {installMutation.error instanceof Error
                  ? installMutation.error.message
                  : "Unknown error"}
              </p>
            ) : null}
          </div>
        </>
      ) : null}
    </Modal>
  );
}
