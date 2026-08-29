'use client';

import { useTranslations } from 'next-intl';

interface TopUsersTableProps {
  data: { user_id: string; cost: number }[];
}

export function TopUsersTable({ data }: TopUsersTableProps) {
  const t = useTranslations('admin');

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">{t('topUsers')}</h2>
      {data.length === 0 ? (
        <p className="text-neutral-500 text-sm py-8 text-center">{t('noData')}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-400 border-b border-neutral-800">
              <th className="text-left py-2 px-3">{t('user')}</th>
              <th className="text-right py-2 px-3">{t('cost')}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((u, i) => (
              <tr key={i} className="border-b border-neutral-800/50">
                <td className="py-2 px-3 text-neutral-300 font-mono text-xs">
                  {u.user_id.slice(0, 12)}…
                </td>
                <td className="py-2 px-3 text-right text-neutral-200">
                  ${u.cost.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
