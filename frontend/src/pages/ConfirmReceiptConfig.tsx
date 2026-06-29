import React, { useEffect, useState } from 'react';
import { getAccounts, getItems, getConfirmReceiptConfig, updateConfirmReceiptConfig } from '../api';

export default function ConfirmReceiptConfig() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [selectedAcc, setSelectedAcc] = useState('');
  const [selectedItem, setSelectedItem] = useState('');
  const [config, setConfig] = useState<any>({ enabled: false, message_content: '', message_image: '', reply_once: true });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getAccounts(1, 100).then(r => r.success && setAccounts(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedAcc) {
      getItems(selectedAcc).then(r => r.success && setItems(r.data)).catch(() => {});
    } else {
      setItems([]);
    }
  }, [selectedAcc]);

  useEffect(() => {
    if (selectedAcc) {
      getConfirmReceiptConfig(selectedAcc, selectedItem || undefined).then(r => {
        if (r.success !== false) {
          setConfig(r);
        }
      }).catch(() => {});
    }
  }, [selectedAcc, selectedItem]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const r = await updateConfirmReceiptConfig(selectedAcc, {
        enabled: config.enabled,
        message_content: config.message_content,
        message_image: config.message_image,
        reply_once: config.reply_once,
        item_id: selectedItem || null,
      });
      if (r.success) alert('保存成功');
    } catch {}
    setSaving(false);
  };

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 20, color: '#2d2d2d' }}>确认收货消息配置</h2>
      <p style={{ fontSize: 13, color: '#8a8a8a', marginBottom: 20 }}>
        配置买家确认收货后自动发送的消息。支持按商品维度配置不同的消息内容。
      </p>

      <div className="neu-card" style={{ maxWidth: 600 }}>
        <div style={{ display: 'grid', gap: 16 }}>
          <div>
            <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>选择账号 *</label>
            <select className="neu-input" value={selectedAcc} onChange={e => { setSelectedAcc(e.target.value); setSelectedItem(''); }}>
              <option value="">请选择账号</option>
              {accounts.map((a: any) => (
                <option key={a.account_id} value={a.account_id}>{a.remark || a.account_id}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>
              绑定商品 <span style={{ color: '#a0a0a0' }}>（留空=所有商品使用此配置）</span>
            </label>
            <select className="neu-input" value={selectedItem} onChange={e => setSelectedItem(e.target.value)}
              disabled={!selectedAcc}>
              <option value="">所有商品（账号级配置）</option>
              {items.map((i: any) => (
                <option key={i.item_id} value={i.item_id} title={i.title || i.item_id}>{i.title || i.item_id}</option>
              ))}
            </select>
            {selectedItem && (
              <p style={{ fontSize: 12, color: '#2d5a8a', marginTop: 4 }}>
                已选择商品：{items.find(i => i.item_id === selectedItem)?.title || selectedItem}
                <br />
                此配置只对该商品生效，其他商品使用"所有商品"配置
              </p>
            )}
          </div>

          {selectedAcc && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div className={'neu-toggle ' + (config.enabled ? 'active' : '')}
                  onClick={() => setConfig({...config, enabled: !config.enabled})} />
                <span style={{ fontSize: 14 }}>启用确认收货消息</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div className={'neu-toggle ' + (config.reply_once ? 'active' : '')}
                  onClick={() => setConfig({...config, reply_once: !config.reply_once})} />
                <span style={{ fontSize: 14 }}>对同一用户只发送一次</span>
              </div>

              <div>
                <label style={{ fontSize: 13, color: '#6a6a6a', display: 'block', marginBottom: 4 }}>消息内容</label>
                <textarea className="neu-input" rows={3}
                  value={config.message_content || ''}
                  onChange={e => setConfig({...config, message_content: e.target.value})}
                  placeholder={'例如：\n感谢您的支持！欢迎下次光临~'}
                  disabled={!config.enabled} />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                <button className="neu-button neu-button-primary" onClick={handleSave} disabled={saving}>
                  {saving ? '保存中...' : '保存配置'}
                </button>
              </div>
            </>
          )}

          {!selectedAcc && (
            <p style={{ textAlign: 'center', padding: 32, color: '#8a8a8a', fontSize: 13 }}>
              请先选择一个账号开始配置
            </p>
          )}
        </div>
      </div>

      <div className="neu-card" style={{ maxWidth: 600, marginTop: 20 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, color: '#2d5a8a' }}>配置说明</h3>
        <ul style={{ fontSize: 13, color: '#6a6a6a', lineHeight: 1.8, paddingLeft: 16 }}>
          <li><strong>账号级配置</strong>（不绑定商品）：该账号下所有商品的确认收货消息</li>
          <li><strong>商品级配置</strong>（绑定具体商品）：仅对该商品生效，覆盖账号级配置</li>
          <li>支持同时配置多个商品的不同消息内容</li>
          <li>启用"只发送一次"后，同一买家不会重复收到消息</li>
        </ul>
      </div>
    </div>
  );
}
