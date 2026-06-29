import React, { useEffect, useState } from 'react';
import { getOverview, getProductionDiagnostics } from '../api';

export default function Dashboard() {
  const [stats, setStats] = useState<any>({});
  const [diagnostics, setDiagnostics] = useState<any>(null);

  useEffect(() => {
    getOverview().then(r => r.success && setStats(r.data)).catch(() => {});
    getProductionDiagnostics().then(r => r.success && setDiagnostics(r)).catch(() => {});
  }, []);

  const cards = [
    { label: '账号总数', value: stats.total_accounts ?? '-' },
    { label: '商品总数', value: stats.total_items ?? '-' },
    { label: '总订单', value: stats.total_orders ?? '-' },
    { label: '今日订单', value: stats.today_orders ?? '-' },
    { label: '近7天消息', value: stats.week_msg_received ?? '-' },
    { label: '近7天回复', value: stats.week_msg_replied ?? '-' },
  ];

  const quickLinks = [
    { label: '账号管理', path: '/accounts', icon: '👥' },
    { label: '商品管理', path: '/items', icon: '📦' },
    { label: '自动回复', path: '/keywords', icon: '💬' },
    { label: '确认收货', path: '/confirm-receipt', icon: '✅' },
    { label: '订单管理', path: '/orders', icon: '🛒' },
    { label: '数据统计', path: '/statistics', icon: '📊' },
  ];

  const missingItems = diagnostics?.items_missing_delivery_configs || [];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 24, color: '#2d2d2d' }}>仪表盘</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16, marginBottom: 32 }}>
        {cards.map((card) => (
          <div key={card.label} className="neu-card stat-card">
            <div className="label">{card.label}</div>
            <div className="value">{card.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="neu-card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: '#2d5a8a' }}>快速入口</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {quickLinks.map((item) => (
              <a key={item.path} href={item.path} className="neu-card-sm" style={{ textDecoration: 'none', color: '#4a4a4a', textAlign: 'center', padding: 16 }}>
                <div style={{ fontSize: 24, marginBottom: 4 }}>{item.icon}</div>
                <div style={{ fontSize: 13 }}>{item.label}</div>
              </a>
            ))}
          </div>
        </div>
        <div className="neu-card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: '#2d5a8a' }}>生产自检</h3>
          <div style={{ fontSize: 13, color: '#6a6a6a', lineHeight: 2 }}>
            {!diagnostics ? (
              <p>正在检查生产状态...</p>
            ) : (
              <>
                <p>
                  状态
                  <span className={'badge ' + (diagnostics.ready ? 'badge-success' : 'badge-warning')} style={{ marginLeft: 8 }}>
                    {diagnostics.ready ? 'Ready' : 'Need action'}
                  </span>
                </p>
                <p>WebSocket：{diagnostics.websocket?.active?.length || 0} / {diagnostics.summary?.active_accounts || 0} 在线</p>
                <p>商品：{diagnostics.summary?.items || 0}　发货配置：{diagnostics.summary?.enabled_delivery_configs || 0}</p>
                <p>待发货：{diagnostics.summary?.pending_orders || 0}　失败：{diagnostics.summary?.failed_delivery_logs || 0}</p>
                {diagnostics.issues?.length ? (
                  <div style={{ marginTop: 8 }}>
                    {diagnostics.issues.map((issue: string) => (
                      <div key={issue} style={{ color: '#b8860b' }}>• {issue}</div>
                    ))}
                  </div>
                ) : (
                  <p style={{ color: '#2d8a4a' }}>基础条件已具备，等待真实订单验证</p>
                )}
                {missingItems.length > 0 && (
                  <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #d8d8d8' }}>
                    <div style={{ color: '#2d5a8a', fontWeight: 600, marginBottom: 4 }}>未开启发货配置的商品</div>
                    {missingItems.slice(0, 5).map((item: any) => (
                      <a key={`${item.account_id}-${item.item_id}`} href="/items" style={{ display: 'block', color: '#6a6a6a', textDecoration: 'none' }}>
                        • {item.title || item.item_id}
                      </a>
                    ))}
                    <a href="/items" className="neu-button" style={{ display: 'inline-block', marginTop: 10, textDecoration: 'none' }}>
                      去商品管理配置发货内容
                    </a>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
