'use client';

import { useTranslations } from 'next-intl';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface SubagentCostBreakdownProps {
  data: { name: string; cost: number; input_tokens: number; output_tokens: number }[];
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

export function SubagentCostBreakdown({ data }: SubagentCostBreakdownProps) {
  const t = useTranslations('admin');

  const chartData = data.map((d) => ({
    name: d.name,
    cost: Number(d.cost.toFixed(4)),
    input_tokens: d.input_tokens,
    output_tokens: d.output_tokens,
  }));

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">{t('subagentBreakdown')}</h2>
      {chartData.length === 0 ? (
        <p className="text-neutral-500 text-sm py-8 text-center">{t('noData')}</p>
      ) : (
        <div className="flex flex-col md:flex-row items-center gap-4">
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="cost"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={(entry: { name?: string }) => entry.name ?? ''}
              >
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a1a1a',
                  border: '1px solid #333',
                  borderRadius: '8px',
                }}
                formatter={(value: unknown) => [`$${Number(value).toFixed(4)}`, t('cost')]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="w-full md:w-auto space-y-2">
            {chartData.map((d, i) => (
              <div key={d.name} className="flex items-center gap-2 text-sm">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="text-neutral-300">{d.name}</span>
                <span className="text-neutral-500 ml-auto">${d.cost.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
