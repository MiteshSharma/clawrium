import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import type { AgentSkills } from "@/lib/types";

// Mocked hook state — each test resets the slots in beforeEach.
const agentSkillsState: {
  data: AgentSkills | undefined;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
} = { data: undefined, isLoading: false, error: null, refetch: vi.fn() };

const installMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
};
const removeMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
};

vi.mock("@/hooks", () => ({
  useAgentSkills: () => agentSkillsState,
  useInstallAgentSkill: () => installMutation,
  useRemoveAgentSkill: () => removeMutation,
}));

vi.mock("@/components/ui/modal", () => ({
  Modal: ({
    open,
    title,
    children,
    footer,
  }: {
    open: boolean;
    title: string;
    children: React.ReactNode;
    footer?: React.ReactNode;
  }) =>
    open ? (
      <div data-testid="modal">
        <p>{title}</p>
        {children}
        {footer}
      </div>
    ) : null,
}));

import { SkillsTab } from "./skills-tab";

function makeAgentSkills(overrides: Partial<AgentSkills> = {}): AgentSkills {
  return {
    agent_name: "tdd-hermes",
    agent_type: "hermes",
    installed: [],
    available: [
      {
        ref: "clawrium/tdd",
        registry: "clawrium",
        name: "tdd",
        description: "TDD discipline.",
        version: "0.1.0",
      },
    ],
    ...overrides,
  };
}

describe("SkillsTab", () => {
  beforeEach(() => {
    agentSkillsState.data = undefined;
    agentSkillsState.isLoading = false;
    agentSkillsState.error = null;
    agentSkillsState.refetch = vi.fn();
    installMutation.mutateAsync = vi.fn().mockResolvedValue({});
    installMutation.isPending = false;
    removeMutation.mutateAsync = vi.fn().mockResolvedValue({});
    removeMutation.isPending = false;
  });

  it("renders the loading skeleton while fetching", () => {
    agentSkillsState.isLoading = true;
    render(<SkillsTab agentKey="tdd-hermes" />);
    expect(screen.getByTestId("skills-loading")).toBeInTheDocument();
  });

  it("renders an error state with a retry control", () => {
    agentSkillsState.error = new Error("boom");
    render(<SkillsTab agentKey="tdd-hermes" />);
    expect(screen.getByText(/Failed to load skills/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(agentSkillsState.refetch).toHaveBeenCalled();
  });

  it("shows the empty-state hint when nothing is installed", () => {
    agentSkillsState.data = makeAgentSkills();
    render(<SkillsTab agentKey="tdd-hermes" />);
    expect(screen.getByText(/No skills installed yet/i)).toBeInTheDocument();
  });

  it("renders installed skills with Remove buttons", () => {
    agentSkillsState.data = makeAgentSkills({
      installed: [
        {
          ref: "clawrium/tdd",
          registry: "clawrium",
          name: "tdd",
          description: "TDD discipline.",
          version: "0.1.0",
        },
      ],
    });
    render(<SkillsTab agentKey="tdd-hermes" />);
    expect(screen.getByText("clawrium/tdd")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Remove clawrium\/tdd/ }),
    ).toBeInTheDocument();
  });

  it("opens the install picker filtered to compatible skills", () => {
    agentSkillsState.data = makeAgentSkills();
    render(<SkillsTab agentKey="tdd-hermes" />);
    fireEvent.click(screen.getByRole("button", { name: /Install skill/ }));
    const modal = screen.getByTestId("modal");
    expect(modal).toBeInTheDocument();
    // The picker shows the available skill that isn't yet installed.
    expect(modal.textContent).toContain("clawrium/tdd");
  });

  it("hides already-installed skills from the picker", () => {
    agentSkillsState.data = makeAgentSkills({
      installed: [
        {
          ref: "clawrium/tdd",
          registry: "clawrium",
          name: "tdd",
          description: "TDD discipline.",
          version: "0.1.0",
        },
      ],
    });
    render(<SkillsTab agentKey="tdd-hermes" />);
    // The Install button disables when nothing is available beyond installed.
    expect(
      screen.getByRole("button", { name: /Install skill/ }),
    ).toBeDisabled();
  });

  it("calls install mutation with parsed registry+name", async () => {
    agentSkillsState.data = makeAgentSkills();
    render(<SkillsTab agentKey="tdd-hermes" />);
    fireEvent.click(screen.getByRole("button", { name: /Install skill/ }));
    fireEvent.click(
      screen.getAllByRole("button", { name: /^Install$/ })[0],
    );
    await waitFor(() =>
      expect(installMutation.mutateAsync).toHaveBeenCalledWith({
        agentKey: "tdd-hermes",
        registry: "clawrium",
        name: "tdd",
      }),
    );
  });

  it("calls remove mutation with parsed registry+name", async () => {
    agentSkillsState.data = makeAgentSkills({
      installed: [
        {
          ref: "clawrium/tdd",
          registry: "clawrium",
          name: "tdd",
          description: "TDD discipline.",
          version: "0.1.0",
        },
      ],
    });
    render(<SkillsTab agentKey="tdd-hermes" />);
    fireEvent.click(
      screen.getByRole("button", { name: /Remove clawrium\/tdd/ }),
    );
    await waitFor(() =>
      expect(removeMutation.mutateAsync).toHaveBeenCalledWith({
        agentKey: "tdd-hermes",
        registry: "clawrium",
        name: "tdd",
      }),
    );
  });

  it("surfaces install errors inline", async () => {
    agentSkillsState.data = makeAgentSkills();
    installMutation.mutateAsync = vi
      .fn()
      .mockRejectedValue(new Error("host unreachable"));
    render(<SkillsTab agentKey="tdd-hermes" />);
    fireEvent.click(screen.getByRole("button", { name: /Install skill/ }));
    fireEvent.click(
      screen.getAllByRole("button", { name: /^Install$/ })[0],
    );
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/host unreachable/);
    });
  });
});
