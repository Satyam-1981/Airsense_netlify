import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function TrendChart({
  data,
  dataKey = "aqi",
  color = "#168b78",
  height = 250,
  label = "AQI estimate",
}) {
  if (!data?.length)
    return (
      <div className="chart-empty">No trend points are available yet.</div>
    );
  return (
    <div className="chart-area" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 10, left: -18, bottom: 4 }}
        >
          <CartesianGrid
            stroke="#e9efeb"
            strokeDasharray="4 5"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: "#82918b", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            minTickGap={22}
          />
          <YAxis
            tick={{ fill: "#82918b", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              border: "1px solid #e4ebe6",
              borderRadius: 12,
              boxShadow: "0 12px 32px #132c2712",
            }}
            formatter={(value) => [Number(value).toFixed(1), label]}
          />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2.8}
            dot={false}
            activeDot={{ r: 5, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
