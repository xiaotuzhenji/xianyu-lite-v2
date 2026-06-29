import React, { useEffect, useState } from 'react';
import { getAccounts, createAccount, updateAccount, deleteAccount, generateQR, getQRStatus, startQRPoll } from '../api';

export default function Accounts() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [showAdd, setShowAdd] = useState(false);
  const [newCookie, setNewCookie] = useState("");
  const [newRemark, setNewRemark] = useState("");
  const [editAcc, setEditAcc] = useState<any>(null);
  const [editRemark, setEditRemark] = useState('');
  const [showQR, setShowQR] = useState(false);
  const [qrSessionId, setQrSessionId] = useState('');
  const [qrUrl, setQrUrl] = useState('');
  const [qrStatus, setQrStatus] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const r = await getAccounts(page);
      if (r.success) { setAccounts(r.data); setTotal(r.total); }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, [page]);

  const handleSave = async (acc: any) => {
    await updateAccount(acc.account_id, { remark: editRemark });
    setEditAcc(null);
    load();
  };

  const handleDelete = async (acc: any) => {
    if (!window.confirm('确认删除账号?')) return;
    await deleteAccount(acc.account_id);
    load();
  };

  const handleAdd = async () => {
    if (!newCookie.trim()) { alert("请填写Cookie"); return; }
    try {
      const r = await createAccount({ cookie: newCookie.trim(), remark: newRemark.trim() });
      if (r.success) { setShowAdd(false); setNewCookie(""); setNewRemark(""); load(); }
      else alert(r.detail || "添加失败");
    } catch (e) { alert("网络错误: " + String(e)); }
  };

  const handleQRLogin = async () => {
    try {
      const r = await generateQR();
      if (r.success) {
        setQrSessionId(r.data.session_id);
        setQrUrl(r.data.qr_code_url);
        setQrStatus('waiting');
        setShowQR(true);
        // Start polling
        await startQRPoll(r.data.session_id);
        // Poll status every 2s
        const poll = setInterval(async () => {
          const s = await getQRStatus(r.data.session_id);
          if (s.success && s.data) {
            setQrStatus(s.data.status);
            if (s.data.status === 'success' || s.data.status === 'expired' || s.data.status === 'cancelled' || s.data.status === 'verification_required') {
              clearInterval(poll);
              if (s.data.status === 'success') {
                alert('扫码成功! 账号: ' + (s.data.account_id || '') + (s.data.is_new ? ' (新账号)' : ' (已更新)'));
                setShowQR(false);
                load();
              }
            }
          }
        }, 2000);
      } else {
        alert('生成二维码失败: ' + (r.message || ''));
      }
    } catch (e) { alert('扫码登录失败: ' + String(e)); }
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: '#2d2d2d' }}>账号管理</h2>
        <button className='neu-button neu-button-primary' style={{ padding: '8px 20px', fontSize: 13 }} onClick={() => setShowAdd(true)}>+ 添加账号</button>
        <button className="neu-button" style={{ padding: '8px 20px', fontSize: 13, marginLeft: 8 }} onClick={handleQRLogin}>··· 扫码登录</button>
      </div>
      <div className="neu-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container"><table>
          <thead><tr><th>账号ID</th><th>备注</th><th>状态</th><th>自动发货</th><th>最后活跃</th><th>操作</th></tr></thead>
          <tbody>
            {accounts.map((acc: any) => (
              <tr key={acc.id}>
                <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{acc.account_id}</td>
                <td>{acc.remark || '-'}</td>
                <td><span className={'badge ' + (acc.status === 'active' ? 'badge-success' : 'badge-warning')}>{acc.status === 'active' ? '正常' : acc.status}</span></td>
                <td>{acc.auto_confirm ? 'Yes' : 'No'}</td>
                <td style={{ fontSize: 13, color: '#8a8a8a' }}>{acc.last_active_at || '-'}</td>
                <td>
                  <button className="neu-button" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => { setEditAcc(acc); setEditRemark(acc.remark || ''); }}>编辑</button>
                  <button className="neu-button" style={{ padding: '6px 12px', fontSize: 12, color: '#c0392b', marginLeft: 4 }} onClick={() => handleDelete(acc)}>删除</button>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: '#8a8a8a' }}>{loading ? '加载中...' : '暂无账号'}</td></tr>}
          </tbody>
        </table></div>
      </div>
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button className="neu-button" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span style={{ padding: '8px 12px', fontSize: 13, color: '#6a6a6a' }}>{page}/{totalPages}</span>
          <button className="neu-button" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}
      {showQR && (
        <div className="modal-overlay" onClick={() => { setShowQR(false); setQrStatus(''); }}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>扫码登录</h3>
            <div style={{ textAlign: 'center', padding: 20 }}>
              {qrStatus === 'waiting' && !qrUrl.startsWith('http') && <p style={{ color: '#888' }}>正在获取二维码...</p>}
              {qrStatus === 'waiting' && qrUrl && <div>
                <img src={qrUrl} alt="QR Code" style={{ width: 200, height: 200, borderRadius: 12 }} />
                <p style={{ marginTop: 12, fontSize: 13, color: '#666' }}>请打开闲鱼App扫描二维码</p>
              </div>}
              {qrStatus === 'scanned' && <div>
                <div style={{ fontSize: 48, marginBottom: 8 }}>&#x2705;</div>
                <p style={{ fontSize: 14, color: '#2d2d2d' }}>已扫码，请在手机上确认登录</p>
              </div>}
              {qrStatus === 'success' && <div>
                <div style={{ fontSize: 48, marginBottom: 8 }}>&#x1F389;</div>
                <p style={{ fontSize: 14, color: '#27ae60' }}>登录成功!</p>
              </div>}
              {qrStatus === 'expired' && <div>
                <div style={{ fontSize: 48, marginBottom: 8 }}>&#x23F0;</div>
                <p style={{ fontSize: 14, color: '#e67e22' }}>二维码已过期，请重新生成</p>
              </div>}
             {qrStatus === 'cancelled' && <div>
              {qrStatus === 'verification_required' && <div>
                <div style={{ fontSize: 48, marginBottom: 8 }}>&#x26A0;</div>
                <p style={{ fontSize: 14, color: '#e67e22' }}>需要手机验证，请打开闲鱼App完成风控验证后重试</p>
              </div>}
                <div style={{ fontSize: 48, marginBottom: 8 }}>&#x274C;</div>
                <p style={{ fontSize: 14, color: '#c0392b' }}>已取消登录</p>
              </div>}
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="neu-button" onClick={() => { setShowQR(false); setQrStatus(''); }}>关闭</button>
             {(qrStatus === 'expired' || qrStatus === 'cancelled') && <button className="neu-button neu-button-primary" onClick={handleQRLogin}>重新生成</button>}
              {(qrStatus === 'expired' || qrStatus === 'cancelled' || qrStatus === 'verification_required') && <button className="neu-button neu-button-primary" onClick={handleQRLogin}>重新生成</button>}
            </div>
          </div>
        </div>
      )}

      {showAdd && (
        <div className="modal-overlay" onClick={() => setShowAdd(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>添加账号</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>Cookie</label>
              <textarea className="neu-input" style={{ minHeight: 80, resize: 'vertical', fontSize: 12 }} value={newCookie} onChange={e => setNewCookie(e.target.value)} placeholder="在浏览器打开闲鱼网页版, 按F12->网络->请求头复制Cookie" />
              <p style={{ fontSize: 11, color: '#999', marginTop: 4, lineHeight: 1.4 }}>系统会自动识别账号ID, 重复添加会更新Cookie。提交后自动开始连接。</p>
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>备注 (可选)</label>
              <input className="neu-input" value={newRemark} onChange={e => setNewRemark(e.target.value)} placeholder="例如: 主账号1" />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
              <button className="neu-button" onClick={() => setShowAdd(false)}>取消</button>
              <button className="neu-button neu-button-primary" onClick={handleAdd}>保存</button>
            </div>
          </div>
        </div>
      )}

      {editAcc && (
        <div className="modal-overlay" onClick={() => setEditAcc(null)}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>编辑账号</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>备注名称</label>
              <input className="neu-input" value={editRemark} onChange={e => setEditRemark(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
              <button className="neu-button" onClick={() => setEditAcc(null)}>取消</button>
              <button className="neu-button neu-button-primary" onClick={() => handleSave(editAcc)}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
