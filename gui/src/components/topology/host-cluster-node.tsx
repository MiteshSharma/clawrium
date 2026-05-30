"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

import { type HostClusterNodeData } from "./topology-graph";

export function HostClusterNode({ data }: NodeProps) {
  const { hostname, alias, agentCount, hostColor, width, height, onHostClick } =
    data as unknown as HostClusterNodeData;

  return (
    <div
      style={{ width, height }}
      className="relative rounded-xl"
    >
      <Handle
        type="target"
        position={Position.Bottom}
        id="ssh"
        className="!bg-transparent !border-0 !w-1 !h-1"
      />
      <div
        className="absolute inset-0 rounded-xl border-2 border-dashed"
        style={{ borderColor: "#EA580C", pointerEvents: "none" }}
      />
      <button
        onClick={() => onHostClick?.(hostname)}
        className="absolute left-4 top-3 flex items-baseline gap-2 hover:opacity-80 transition-opacity"
      >
        <span
          className="inline-block w-2.5 h-2.5 rounded-full self-center"
          style={{ backgroundColor: hostColor }}
        />
        <span className="text-base font-bold text-primary-text">{alias}</span>
        <span className="text-[11px] text-muted">·</span>
        <span className="text-[11px] text-muted truncate max-w-[280px]">
          {hostname}
        </span>
        <span className="text-[11px] text-muted">·</span>
        <span className="text-[11px] text-muted">
          {agentCount} {agentCount === 1 ? "agent" : "agents"}
        </span>
      </button>
    </div>
  );
}
