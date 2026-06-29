import React, { useEffect, useState } from 'react';
import { getOverview, getDailyStats } from '../api';

export default function Statistics() {
  const [overview, setOverview] = useState<any>({});
  const [dailyStats, setDailyStats] = useState<any[]>([]);

  useEffect(() => {
    getOverview().then(r => r.success && setOverview(r.data)).catch(() => {});
    getDailyStats(14).then(r => r.success && setDailyStats(r.data)).catch(() => {});
  }, []);

  const cards = [
    { label: '账号总数', value: overview.total_accounts ?? '-' },
    { label: '商品总数', value: overview.total_items ?? '-' },
    { label: '总订单', value: overview.total_orders ?? '-' },
    { label: '今日订单', value: overview.today_orders ?? '-' },
    { label: '近7天消息', value: overview.week_msg_received ?? '-' },
    { label: '近7天回复', value: overview.week_msg_replied ?? '-' },
    { label: '近7天交易额', value: overview.week_order_amount ? '¥' + overview.week_order_amount : '-' },
  ];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 24, color: '#2d2d2d' }}>数据统计</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 14, marginBottom: 28 }}>
        {cards.map((c: any) => (<div key={c.label} className="neu-card stat-card"><div className="label">{c.label}</div><div className="value" style={{ fontSize: 24 }}>{c.value}</div></div>))}
      </div>
      <div className="neu-card">
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: '#2d5a8a' }}>近14天每日统计</h3>
        {dailyStats.length === 0 ? (
          <p style={{ textAlign: 'center', padding: 24, color: '#8a8a8a', fontSize: 13 }}>暂无数据</p>
        ) : (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {dailyStats.map((s: any) => (
              <div key={s.stat_date} className="neu-card-sm" style={{ minWidth: 100, textAlign: 'center', padding: 12 }}>
                <div style={{ fontSize: 12, color: '#8a8a8a' }}>{s.stat_date?.slice(5)}</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#2d5a8a', marginTop: 4 }}>{s.orders_count || 0}</div>
                <div style={{ fontSize: 11, color: '#6a6a6a' }}>订单</div>
                <div style={{ fontSize: 13, color: '#2d8a4a', marginTop: 2 }}>¥{s.orders_amount || 0}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
