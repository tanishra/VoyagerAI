'use client';

import { useTranslations } from 'next-intl';
import { AlertTriangle } from 'lucide-react';

interface TokenEfficiencyTableProps {
  data: { thread_id: string; user_id: string; efficiency_ratio: number; cost: number }[];
}

export function TokenEfficiencyTable({ data }: TokenEfficiencyTableProps) {
  const t = useTranslations('admin');

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-5 h-5 text-amber-400" />
        <h2 className="text-lg font-semibold">{t('tokenEfficiency')}</h2>
      </div>
      {data.length === 0 ? (
        <p className="text-neutral-500 text-sm py-8 text-center">{t('noData')}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-400 border-b border-neutral-800">
              <th className="text-left py-2 px-3">{t('threadId')}</th>
              <th className="text-left py-2 px-3">{t('user')}</th>
              <th className="text-right py-2 px-3">{t('efficiencyRatio')}</th>
              <th className="text-right py-2 px-3">{t('cost')}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s, i) => (
              <tr key={i} className="border-b border-neutral-800/50">
                <td className="py-2 px-3 text-neutral-300 font-mono text-xs">
                  {s.thread_id.slice(0, 12)}…
                </td>
                <td className="py-2 px-3 text-neutral-300 font-mono text-xs">
                  {s.user_id.slice(0, 12)}…
                </td>
                <td className="py-2 px-3 text-right text-red-400">
                  {s.efficiency_ratio.toFixed(1)}:1
                </td>
                <td className="py-2 px-3 text-right text-neutral-200">
                  ${s.cost.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
