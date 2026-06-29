import React, { useEffect, useState } from 'react';
import { getKeywords, createKeyword, deleteKeyword, getAccounts, getItems } from '../api';
import { Plus, Trash2 } from 'lucide-react';

export default function Keywords() {
  const [keywords, setKeywords] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [accFilter, setAccFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ account_id: '', keyword: '', reply_content: '', item_id: '' });

  const load = async () => {
    setLoading(true);
    try {
      const r = await getKeywords(accFilter || undefined);
      if (r.success) setKeywords(r.data);
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    getAccounts(1, 100).then(r => r.success && setAccounts(r.data)).catch(() => {});
    getItems().then(r => r.success && setItems(r.data)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [accFilter]);

  const handleCreate = async () => {
    if (!form.account_id || !form.keyword) return;
    const r = await createKeyword({
      account_id: form.account_id,
      keyword: form.keyword,
      reply_content: form.reply_content,
      item_id: form.item_id || undefined,
    });
    if (r.success) {
      setShowForm(false);
      setForm({ account_id: '', keyword: '', reply_content: '', item_id: '' });
      load();
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除?')) return;
    await deleteKeyword(id);
    load();
  };

  const itemOptions = items.filter(i => !form.item_id || form.item_id === '');

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: '#2d2d2d' }}>自动回复</h2>
        <button className="neu-button neu-button-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={16} style={{ marginRight: 4, display: 'inline' }} />
          新增关键词
        </button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <select className="neu-input" style={{ width: 200 }} value={accFilter} onChange={e => setAccFilter(e.target.value)}>
          <option value="">全部账号</option>
          {accounts.map((a: any) => (
            <option key={a.account_id} value={a.account_id}>{a.remark || a.account_id}</option>
          ))}
        </select>
      </div>

      {showForm && (
        <div className="neu-card" style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: '#2d5a8a' }}>新增关键词规则</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>选择账号 *</label>
              <select className="neu-input" value={form.account_id} onChange={e => setForm({...form, account_id: e.target.value})}>
                <option value="">请选择</option>
                {accounts.map((a: any) => (
                  <option key={a.account_id} value={a.account_id}>{a.remark || a.account_id}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>绑定商品（可选）</label>
              <select className="neu-input" value={form.item_id} onChange={e => setForm({...form, item_id: e.target.value})}>
                <option value="">通用（所有商品）</option>
                {items.map((i: any) => (
                  <option key={i.item_id} value={i.item_id} title={i.title || i.item_id}>{i.title || i.item_id}</option>
                ))}
              </select>
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>关键词（一行一个） *</label>
              <textarea className="neu-input" rows={2} value={form.keyword} onChange={e => setForm({...form, keyword: e.target.value})}
                placeholder="例如：&#10;价格&#10;多少钱&#10;包邮" />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>回复内容</label>
              <textarea className="neu-input" rows={2} value={form.reply_content} onChange={e => setForm({...form, reply_content: e.target.value})}
                placeholder="自动回复的内容，可用 {send_user_name} 变量" />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <button className="neu-button" onClick={() => setShowForm(false)}>取消</button>
            <button className="neu-button neu-button-primary" onClick={handleCreate}>创建</button>
          </div>
        </div>
      )}

      <div className="neu-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>账号</th>
                <th>关键词</th>
                <th>回复内容</th>
                <th>绑定商品</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {keywords.map((kw: any) => (
                <tr key={kw.id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{kw.account_id}</td>
                  <td style={{ fontSize: 13 }}>{kw.keyword}</td>
                  <td style={{ maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13 }}>
                    {kw.reply_content || (kw.reply_type === 'image' ? '图片回复' : '-')}
                  </td>
                  <td>{kw.item_id ? <span className="badge badge-success" style={{ fontSize: 11 }}>{kw.item_id.slice(0, 8)}...</span> : <span style={{ color: '#8a8a8a', fontSize: 13 }}>通用</span>}</td>
                  <td>
                    <button className="neu-button" style={{ padding: '6px 10px', fontSize: 12, color: '#c0392b' }}
                      onClick={() => handleDelete(kw.id)}>
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
              {keywords.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 32, color: '#8a8a8a' }}>
                  {loading ? '加载中...' : '暂无关键词规则，点击右上角新增'}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
