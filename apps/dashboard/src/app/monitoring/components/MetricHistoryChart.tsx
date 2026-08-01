"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";

export interface MetricPoint {
  time: string;
  value: number;
}

interface MetricHistoryChartProps {
  data: MetricPoint[];
  color?: string;
}

export default function MetricHistoryChart({
  data,
  color = "#22d3ee",
}: MetricHistoryChartProps) {
  return (
    <div className="h-20 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Tooltip
            contentStyle={{
              background: "#08111f",
              border: "1px solid #1e293b",
              borderRadius: 10,
              color: "#ffffff",
            }}
            labelStyle={{
              color: "#94a3b8",
            }}
          />

          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={3}
            dot={false}
            isAnimationActive
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
