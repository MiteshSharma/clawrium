import { MarkerType, type Edge, type Node } from "@xyflow/react";

import {
  type AcceleratorVendor,
  type TopologyAgent,
  type TopologyResponse,
} from "@/lib/types";
import { buildHostColorMap, getHostColor } from "./host-colors";
import { AGENT_NODE_WIDTH } from "./agent-node";

/* ─── Layout Constants ────────────────────────────────────────────── */

/** Fixed agent card height used for cluster layout math. The rendered
 * card height is roughly content-driven (~150-160px); this value is a
 * conservative upper bound so the cluster border encloses all agents. */
const AGENT_NODE_HEIGHT = 160;

/** Max agents per row within a single cluster before wrapping. */
const MAX_AGENTS_PER_CLUSTER_ROW = 3;

/** Intra-cluster spacing between agent cards. */
const AGENT_GAP_X = 36;
const AGENT_GAP_Y = 20;

/** Cluster padding (header occupies the extra top room). */
const CLUSTER_PAD_X = 18;
const CLUSTER_PAD_TOP = 44;
const CLUSTER_PAD_BOTTOM = 18;

/** Inter-cluster spacing on the canvas. */
const CLUSTER_GAP_X = 56;
const CLUSTER_GAP_Y = 48;

/** Width budget used for greedy width-fit cluster packing. Clusters
 * pack left-to-right until the next would exceed this width, then a
 * new canvas row starts. */
const CANVAS_WIDTH_TARGET = 1700;

/** Vertical gaps between cluster stack, provider row, and control. */
const PROVIDER_OFFSET_Y = 100;
const CONTROL_OFFSET_Y = 220;

/** Horizontal spacing between provider nodes. */
const PROVIDER_SPACING = 200;

const UNCONFIGURED_KEY = "__unconfigured__";

/* ─── Types ───────────────────────────────────────────────────────── */

export interface ProviderNodeData {
  providerKey: string;
  name: string;
  type: string | null;
  endpoint: string | null;
  model: string | null;
  agentCount: number;
  unconfigured: boolean;
  hostGpuVendor?: string | null;
  /** User-selected accelerator brand for local-inference providers. */
  acceleratorVendor?: AcceleratorVendor | null;
}

export interface HostClusterNodeData {
  hostname: string;
  alias: string;
  agentCount: number;
  hostColor: string;
  width: number;
  height: number;
  onHostClick?: (hostname: string) => void;
}

export interface ComputeTopologyOptions {
  onAgentClick?: (agent: TopologyAgent, hostAlias: string) => void;
  onHostClick?: (hostname: string) => void;
}

interface ProviderAccumulator {
  key: string;
  name: string;
  type: string | null;
  endpoint: string | null;
  unconfigured: boolean;
  /** GPU vendor of the first host (for NVIDIA local inference detection) */
  hostGpuVendor: string | null;
  /** User-selected accelerator brand from provider record. */
  acceleratorVendor: AcceleratorVendor | null;
  agents: Array<{ hostname: string; agentKey: string; model: string | null }>;
}

interface ClusterLayout {
  host: TopologyResponse["hosts"][number];
  cols: number;
  rows: number;
  width: number;
  height: number;
  /** Canvas-absolute top-left of the cluster (set during packing). */
  x: number;
  y: number;
}

/* ─── Helpers ─────────────────────────────────────────────────────── */

export function providerNodeKey(agent: TopologyAgent): string {
  if (!agent.provider && !agent.provider_type) return UNCONFIGURED_KEY;
  const type = agent.provider_type || "unknown";
  const name = agent.provider || type;
  const endpoint = agent.provider_endpoint ?? "";
  return [type, name, endpoint].map(encodeURIComponent).join("|");
}

function measureCluster(agentCount: number): {
  cols: number;
  rows: number;
  width: number;
  height: number;
} {
  const cols = Math.min(agentCount, MAX_AGENTS_PER_CLUSTER_ROW);
  const rows = Math.ceil(agentCount / cols);
  const contentWidth =
    cols * AGENT_NODE_WIDTH + Math.max(cols - 1, 0) * AGENT_GAP_X;
  const contentHeight =
    rows * AGENT_NODE_HEIGHT + Math.max(rows - 1, 0) * AGENT_GAP_Y;
  return {
    cols,
    rows,
    width: contentWidth + CLUSTER_PAD_X * 2,
    height: contentHeight + CLUSTER_PAD_TOP + CLUSTER_PAD_BOTTOM,
  };
}

/** Pack clusters greedily across canvas rows; centre each row on x=0. */
function packClusters(clusters: ClusterLayout[]): void {
  let cursorX = 0;
  let cursorY = 0;
  let rowMaxHeight = 0;

  const rowEnds: number[] = [];
  const rowWidths: number[] = [];

  const flushRow = (endIdx: number) => {
    const widthOfRow = cursorX === 0 ? 0 : cursorX - CLUSTER_GAP_X;
    rowEnds.push(endIdx);
    rowWidths.push(widthOfRow);
  };

  clusters.forEach((cluster, idx) => {
    const wouldOverflow =
      cursorX > 0 && cursorX + cluster.width > CANVAS_WIDTH_TARGET;
    if (wouldOverflow) {
      flushRow(idx);
      cursorY += rowMaxHeight + CLUSTER_GAP_Y;
      cursorX = 0;
      rowMaxHeight = 0;
    }
    cluster.x = cursorX;
    cluster.y = cursorY;
    cursorX += cluster.width + CLUSTER_GAP_X;
    if (cluster.height > rowMaxHeight) rowMaxHeight = cluster.height;
  });
  if (clusters.length > (rowEnds.at(-1) ?? 0)) flushRow(clusters.length);

  // Centre each row on x=0.
  let from = 0;
  rowEnds.forEach((to, rowIdx) => {
    const shift = -rowWidths[rowIdx] / 2;
    for (let i = from; i < to; i++) clusters[i].x += shift;
    from = to;
  });
}

/* ─── Main Layout Function ────────────────────────────────────────── */

export function computeTopology(
  data: TopologyResponse,
  opts: ComputeTopologyOptions = {}
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Build host color map over all hosts (stable colours regardless of
  // which hosts are populated).
  const hostColorMap = buildHostColorMap(data.hosts.map((h) => h.hostname));

  // ─── 1. Host clusters + agent nodes ──────────────────────────────
  // Hosts with zero agents are filtered out — they should not appear.
  const populatedHosts = data.hosts.filter((h) => h.agents.length > 0);

  const clusters: ClusterLayout[] = populatedHosts.map((host) => {
    const { cols, rows, width, height } = measureCluster(host.agents.length);
    return { host, cols, rows, width, height, x: 0, y: 0 };
  });

  packClusters(clusters);

  let clustersBottom = 0;

  clusters.forEach((cluster) => {
    const { host, cols, x: cx, y: cy, width, height } = cluster;
    const hostColor = getHostColor(hostColorMap, host.hostname);

    nodes.push({
      id: `host-cluster-${host.hostname}`,
      type: "host-cluster",
      position: { x: cx, y: cy },
      data: {
        hostname: host.hostname,
        alias: host.alias,
        agentCount: host.agents.length,
        hostColor,
        width,
        height,
        onHostClick: opts.onHostClick,
      } satisfies HostClusterNodeData,
      zIndex: -1,
      selectable: false,
      draggable: false,
    });

    host.agents.forEach((agent, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const ax = cx + CLUSTER_PAD_X + col * (AGENT_NODE_WIDTH + AGENT_GAP_X);
      const ay = cy + CLUSTER_PAD_TOP + row * (AGENT_NODE_HEIGHT + AGENT_GAP_Y);
      nodes.push({
        id: `agent-${agent.agent_key}`,
        type: "agent",
        position: { x: ax, y: ay },
        data: {
          agent,
          hostname: host.hostname,
          hostAlias: host.alias,
          hardware: host.hardware ?? null,
          hostOsFamily: host.os_family ?? null,
          hostColor,
          onAgentClick: opts.onAgentClick,
          onHostClick: opts.onHostClick,
        },
      });
    });

    const bottom = cy + height;
    if (bottom > clustersBottom) clustersBottom = bottom;
  });

  // ─── 2. Provider nodes (below cluster stack) ─────────────────────
  const providerOrder: string[] = [];
  const providerMap = new Map<string, ProviderAccumulator>();

  data.hosts.forEach((host) => {
    host.agents.forEach((agent) => {
      const pKey = providerNodeKey(agent);
      let acc = providerMap.get(pKey);
      if (!acc) {
        const unconfigured = pKey === UNCONFIGURED_KEY;
        acc = {
          key: pKey,
          name: unconfigured
            ? "Unconfigured"
            : agent.provider || agent.provider_type || "Unknown",
          type: unconfigured ? null : agent.provider_type ?? null,
          endpoint: unconfigured ? null : agent.provider_endpoint ?? null,
          unconfigured,
          hostGpuVendor: host.hardware?.gpu?.vendor ?? null,
          acceleratorVendor: agent.provider_accelerator_vendor ?? null,
          agents: [],
        };
        providerMap.set(pKey, acc);
        providerOrder.push(pKey);
      }
      acc.agents.push({
        hostname: host.hostname,
        agentKey: agent.agent_key,
        model: agent.model || null,
      });
    });
  });

  const providerRowY = clustersBottom + PROVIDER_OFFSET_Y;
  const providerCount = providerOrder.length;
  const providerStartX = -((providerCount - 1) * PROVIDER_SPACING) / 2;

  providerOrder.forEach((pKey, idx) => {
    const acc = providerMap.get(pKey)!;
    const providerNodeId = `provider-${pKey}`;
    const providerModel = acc.agents.find((a) => a.model)?.model ?? null;
    nodes.push({
      id: providerNodeId,
      type: "provider",
      position: { x: providerStartX + idx * PROVIDER_SPACING, y: providerRowY },
      data: {
        providerKey: pKey,
        name: acc.name,
        type: acc.type,
        endpoint: acc.endpoint,
        model: providerModel,
        agentCount: acc.agents.length,
        unconfigured: acc.unconfigured,
        hostGpuVendor: acc.hostGpuVendor,
        acceleratorVendor: acc.acceleratorVendor,
      } satisfies ProviderNodeData,
    });

    acc.agents.forEach(({ agentKey }) => {
      const stroke = acc.unconfigured ? "#94A3B8" : "#475569";
      edges.push({
        id: `edge-${agentKey}-${pKey}`,
        source: `agent-${agentKey}`,
        sourceHandle: "provider",
        target: providerNodeId,
        type: "default",
        animated: false,
        style: {
          stroke,
          strokeWidth: 1.25,
          ...(acc.unconfigured ? { strokeDasharray: "4 3" } : {}),
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: stroke,
          width: 14,
          height: 14,
        },
      });
    });
  });

  // ─── 3. Control node + SSH edges ─────────────────────────────────
  const controlRowY = providerRowY + CONTROL_OFFSET_Y;
  nodes.push({
    id: "control",
    type: "control",
    position: { x: 0, y: controlRowY },
    data: { label: data.control.label, description: data.control.description },
  });

  populatedHosts.forEach((host) => {
    edges.push({
      id: `edge-control-${host.hostname}`,
      source: "control",
      target: `host-cluster-${host.hostname}`,
      targetHandle: "ssh",
      type: "default",
      animated: true,
      style: { stroke: "#0D9488", strokeWidth: 1.5, strokeDasharray: "5 3" },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: "#0D9488",
        width: 14,
        height: 14,
      },
      label: "SSH",
      labelStyle: { fontSize: 10, fill: "#475569" },
      labelBgStyle: { fill: "#FFFFFF", fillOpacity: 0.85 },
      labelBgPadding: [3, 1] as [number, number],
    });
  });

  return { nodes, edges };
}
