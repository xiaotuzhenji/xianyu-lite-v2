import React, { useEffect, useState } from 'react';
import { deliverOrder, getAccounts, getOrders, syncOrders } from '../api';

const statusLabels: Record<string, string> = {
  pending_payment: '待付款',
  pending: '待处理',
  paid: '待发货',
  shipped: '已发货',
  received: '已收货',
  rated: '已评价',
  closed: '已关闭',
  refunding: '退款中',
  refunded: '已退款',
};

export default function Orders() {
  const [orders, setOrders] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accFilter, setAccFilter] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await getOrders(accFilter || undefined, page);
      if (r.success) {
        setOrders(r.data);
        setTotal(r.total);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    getAccounts(1, 100).then(r => r.success && setAccounts(r.data)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [accFilter, page]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const r = await syncOrders(accFilter || undefined);
      if (r.success) {
        alert(`同步完成：${r.synced || 0} 个订单` + (r.errors?.length ? `，失败 ${r.errors.length} 个账号` : ''));
        load();
      } else {
        alert(r.detail || r.error || '同步失败');
      }
    } catch (e) { alert('同步失败: ' + String(e)); }
    setSyncing(false);
  };

  const manualDeliver = async (orderId: string) => {
    if (!window.confirm('确认手动触发发货？')) return;
    const r = await deliverOrder(orderId);
    alert(r.success ? '发货成功' : (r.data?.error || r.error || '发货失败'));
    load();
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 20, color: '#2d2d2d' }}>订单管理</h2>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <select className="neu-input" style={{ width: 200 }} value={accFilter} onChange={e => { setAccFilter(e.target.value); setPage(1); }}>
          <option value="">全部账号</option>
          {accounts.map((a: any) => (
            <option key={a.account_id} value={a.account_id}>{a.remark || a.account_id}</option>
          ))}
        </select>
        <button className="neu-button neu-button-primary" disabled={syncing} onClick={handleSync}>{syncing ? '同步中...' : '同步待发货订单'}</button>
      </div>

      <div className="neu-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr><th>订单ID</th><th>账号</th><th>商品</th><th>买家</th><th>金额</th><th>状态</th><th>操作</th></tr>
            </thead>
            <tbody>
              {orders.map((o: any) => (
                <tr key={o.order_id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{o.order_id}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{o.account_id}</td>
                  <td style={{ fontSize: 13 }}>{o.item_id || '-'}</td>
                  <td>{o.buyer_name || o.buyer_id || '-'}</td>
                  <td>¥{o.price}</td>
                  <td><span className="badge">{statusLabels[o.status] || o.status}</span></td>
                  <td><button className="neu-button" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => manualDeliver(o.order_id)}>手动发货</button></td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: '#8a8a8a' }}>
                  {loading ? '加载中...' : '暂无订单，请先同步订单'}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button className="neu-button" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span style={{ padding: '8px 12px', fontSize: 13, color: '#6a6a6a' }}>{page}/{totalPages}</span>
          <button className="neu-button" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}
    </div>
  );
}
