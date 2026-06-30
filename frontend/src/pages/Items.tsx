import React, { useEffect, useMemo, useState } from 'react';
import {
  createItem,
  deleteItem,
  getAccounts,
  getDeliveryConfig,
  getItems,
  offlineItem,
  saveDeliveryConfig,
  syncItems,
  updateItem,
  uploadItemImage,
  publishItem,
} from '../api';

const MAX_ITEM_IMAGES = 8;

const emptyForm = {
  account_id: '',
  item_id: '',
  title: '',
  price: 0,
  url: '',
  description: '',
  image_urls: '[]',
};

function parseImageUrls(value: string) {
  if (!value) return [];
  const urls: string[] = [];
  const seen = new Set<string>();
  const visited = new WeakSet<object>();

  const add = (candidate: unknown) => {
    if (typeof candidate !== 'string') return;
    const text = candidate.trim();
    if (!text || seen.has(text)) return;
    if (/^(https?:\/\/|\/)/i.test(text)) {
      seen.add(text);
      urls.push(text);
    }
  };

  const visit = (node: unknown) => {
    if (!node || urls.length >= MAX_ITEM_IMAGES) return;
    if (typeof node === 'string') {
      const text = node.trim();
      if (!text) return;
      if (text.startsWith('{') || text.startsWith('[')) {
        try {
          visit(JSON.parse(text));
          return;
        } catch {}
      }
      add(text);
      return;
    }
    if (Array.isArray(node)) {
      if (visited.has(node)) return;
      visited.add(node);
      node.forEach((item) => visit(item));
      return;
    }
    if (node && typeof node === 'object') {
      if (visited.has(node as object)) return;
      visited.add(node as object);
      const record = node as Record<string, unknown>;
      ['picUrl', 'picurl', 'imgUrl', 'imageUrl', 'url', 'largePicUrl', 'bigPicUrl', 'smallPicUrl', 'originalPicUrl'].forEach((key) => add(record[key]));
      ['picUrls', 'picUrlList', 'imageUrls', 'images', 'pics', 'list', 'urls', 'items'].forEach((key) => visit(record[key]));
      Object.values(record).forEach((item) => visit(item));
    }
  };

  try {
    visit(JSON.parse(value));
  } catch {
    add(value);
  }

  return urls;
}

export default function Items() {
  const [items, setItems] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accFilter, setAccFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [deliveryContent, setDeliveryContent] = useState('');
  const [deliveryEnabled, setDeliveryEnabled] = useState(true);
  const [itemForm, setItemForm] = useState<any>(emptyForm);
  const [itemModalOpen, setItemModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  const imageList = useMemo(() => parseImageUrls(itemForm.image_urls), [itemForm.image_urls]);

  const load = async () => {
    setLoading(true);
    try {
      const r = await getItems(accFilter || undefined);
      if (r.success) setItems(r.data || []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    getAccounts(1, 100).then((r) => r.success && setAccounts(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [accFilter]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const r = await syncItems(accFilter || undefined);
      if (r.success) {
        alert(`同步完成：${r.synced || 0} 个商品${r.offline ? `，标记下架 ${r.offline} 个` : ''}${r.errors?.length ? `，失败 ${r.errors.length} 个账号` : ''}`);
        load();
      } else {
        alert(r.detail || r.error || '同步失败');
      }
    } catch (e) {
      alert('同步失败：' + String(e));
    }
    setSyncing(false);
  };

  const handlePublish = async (item: any) => {
    const confirmText = item.publish_status === 'published' ? '该商品已上架，确认按当前编辑内容再次发布到闲鱼吗？' : '确认发布该商品到闲鱼？';
    if (!window.confirm(confirmText)) return;
    setPublishing(true);
    try {
      const r = await publishItem(item.item_id);
      if (r.success) {
        alert('发布任务已提交，后台正在执行，请稍候...');
        load();
        pollPublishStatus(item);
      } else {
        alert(r.detail || r.message || '发布失败');
      }
    } catch (e) {
      alert('请求失败：' + String(e));
    }
    setPublishing(false);
  };

  const handleOffline = async (item: any) => {
    if (item.publish_status === 'publishing') {
      alert('商品正在发布中，暂不能下架');
      return;
    }
    if (!window.confirm('确认下架这个商品吗？')) return;
    try {
      const r = await offlineItem(item.item_id);
      if (r.success) {
        alert('下架成功');
        load();
      } else {
        alert(r.detail || r.message || '下架失败');
      }
    } catch (e) {
      alert('请求失败：' + String(e));
    }
  };

  const pollPublishStatus = (sourceItem: any) => {
    let checks = 0;
    const maxChecks = 60;
    let sawPublishing = false;
    const sourceIsDraft = String(sourceItem.item_id || '').startsWith('draft-');
    const sourceWasPublished = sourceItem.publish_status === 'published' && !sourceIsDraft;
    const interval = setInterval(async () => {
      checks++;
      try {
        const r = await getItems();
        if (r.success && r.data) {
          const found = r.data.find((i: any) => i.item_id === sourceItem.item_id);
          const replacement = r.data.find((i: any) =>
            (Number(i.id || 0) > Number(sourceItem.id || 0) || (sourceIsDraft && Number(i.id || 0) === Number(sourceItem.id || 0))) &&
            i.item_id !== sourceItem.item_id &&
            i.account_id === sourceItem.account_id &&
            i.title === sourceItem.title &&
            Number(i.price || 0) === Number(sourceItem.price || 0) &&
            i.status === 'online' &&
            i.publish_status === 'published'
          );
          if (found?.publish_status === 'publishing') {
            sawPublishing = true;
          }
          const failed = [found, replacement].find((item) => item?.publish_status === 'failed');
          const errored = [found, replacement].find((item) => item?.publish_error);
          if (failed) {
            clearInterval(interval);
            load();
            alert('发布失败：' + (failed.publish_error || '未知错误'));
            return;
          } else if (errored) {
            clearInterval(interval);
            load();
            alert(errored.publish_error);
            return;
          } else if (replacement || (!sourceWasPublished && found?.publish_status === 'published') || (sourceWasPublished && sawPublishing && found?.publish_status === 'published')) {
            clearInterval(interval);
            load();
            alert('发布成功');
            return;
          }
        }
      } catch {}
      if (checks >= maxChecks) {
        clearInterval(interval);
        load();
        alert('发布仍在后台处理中，请稍后刷新或同步商品查看结果');
      }
    }, 3000);
  };


  const openNew = () => {
    setItemForm({
      ...emptyForm,
      account_id: accFilter || (accounts[0]?.account_id || ''),
    });
    setItemModalOpen(true);
  };

  const openEdit = (item: any) => {
    setItemForm({
      account_id: item.account_id || '',
      item_id: item.item_id || '',
      title: item.title || '',
      price: item.price || 0,
      url: item.url || '',
      description: item.description || '',
      image_urls: item.image_urls || '[]',
    });
    setItemModalOpen(true);
  };

  const closeItemModal = () => {
    setItemForm(emptyForm);
    setItemModalOpen(false);
  };

  const updateImageUrls = (urls: string[]) => {
    setItemForm({ ...itemForm, image_urls: JSON.stringify(urls) });
  };

  const handleUploadImage = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []) as File[];
    if (!files.length) return;
    if (imageList.length >= MAX_ITEM_IMAGES) {
      alert(`最多上传 ${MAX_ITEM_IMAGES} 张商品图片`);
      event.target.value = '';
      return;
    }
    setUploading(true);
    try {
      const nextUrls = [...imageList];
      for (const file of files.slice(0, MAX_ITEM_IMAGES - imageList.length)) {
        const r = await uploadItemImage(file);
        if (r.success && r.data?.url) {
          nextUrls.push(r.data.url);
        } else {
          alert(r.detail || r.error || `图片上传失败：${file.name}`);
          break;
        }
      }
      if (files.length > MAX_ITEM_IMAGES - imageList.length) {
        alert(`最多保留 ${MAX_ITEM_IMAGES} 张商品图片，超出的图片已跳过`);
      }
      updateImageUrls(nextUrls);
    } catch (e) {
      alert('图片上传失败：' + String(e));
    }
    event.target.value = '';
    setUploading(false);
  };

  const handleRemoveImage = (url: string) => {
    updateImageUrls(imageList.filter((item: string) => item !== url));
  };

  const saveItem = async () => {
    if (!itemForm.account_id.trim()) {
      alert('请选择账号');
      return;
    }
    if (!itemForm.title.trim()) {
      alert('请填写商品标题');
      return;
    }
    const price = Number(itemForm.price || 0);
    if (!Number.isFinite(price) || price < 0) {
      alert('商品价格不能为负数');
      return;
    }
    const payload = {
      account_id: itemForm.account_id.trim(),
      item_id: itemForm.item_id.trim(),
      title: itemForm.title.trim(),
      price,
      url: itemForm.url.trim(),
      description: itemForm.description.trim(),
      image_urls: itemForm.image_urls.trim() || '[]',
    };
    const r = itemForm.item_id ? await updateItem(itemForm.item_id, payload) : await createItem(payload);
    if (r.success) {
      alert(itemForm.item_id ? '商品草稿已更新' : '商品草稿已创建');
      closeItemModal();
      load();
    } else {
      alert(r.detail || r.error || '保存失败');
    }
  };

  const removeItem = async (item: any) => {
    if (item.status === 'online' && !String(item.item_id || '').startsWith('draft-')) {
      alert('请先下架后再删除');
      return;
    }
    if (!window.confirm('确认删除该商品？')) return;
    const r = await deleteItem(item.item_id);
    if (r.success) {
      alert('商品已删除');
      load();
    } else {
      alert(r.detail || r.error || '删除失败');
    }
  };

  const openDelivery = async (item: any) => {
    setEditing(item);
    setDeliveryContent('');
    setDeliveryEnabled(true);
    const r = await getDeliveryConfig(item.account_id, item.item_id);
    if (r.success && r.data) {
      setDeliveryContent(r.data.delivery_content || '');
      setDeliveryEnabled(Boolean(r.data.enabled));
    }
  };

  const saveDelivery = async () => {
    if (!editing) return;
    if (deliveryEnabled && !deliveryContent.trim()) {
      alert('启用自动发货时必须填写发货内容');
      return;
    }
    const r = await saveDeliveryConfig(editing.account_id, {
      item_id: editing.item_id,
      enabled: deliveryEnabled,
      delivery_type: 'text',
      delivery_content: deliveryContent,
      send_once: true,
    });
    if (r.success) {
      alert('发货配置已保存');
      setEditing(null);
    } else {
      alert(r.detail || r.error || '保存失败');
    }
  };

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 20, color: '#2d2d2d' }}>商品管理</h2>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <select className="neu-input" style={{ width: 200 }} value={accFilter} onChange={(e) => setAccFilter(e.target.value)}>
          <option value="">全部账号</option>
          {accounts.map((a: any) => (
            <option key={a.account_id} value={a.account_id}>
              {a.remark || a.account_id}
            </option>
          ))}
        </select>
        <button className="neu-button neu-button-primary" disabled={syncing} onClick={handleSync}>
          {syncing ? '同步中...' : '同步商品'}
        </button>
        <button className="neu-button" onClick={openNew}>新建草稿</button>
      </div>

      <div className="neu-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container">
          <table className="items-table">
            <thead>
              <tr>
                <th>图片</th>
                <th>商品ID</th>
                <th>账号</th>
                <th>标题</th>
                <th>描述</th>
                <th>价格</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item: any) => {
                const firstImage = parseImageUrls(item.image_urls || '[]')[0];
                return (
                  <tr key={item.id}>
                    <td style={{ width: 72 }}>
                      {firstImage ? (
                        <img
                          src={firstImage}
                          alt={item.title || '商品图片'}
                          style={{ width: 52, height: 52, objectFit: 'cover', borderRadius: 10 }}
                        />
                      ) : (
                        <div
                          style={{
                            width: 52,
                            height: 52,
                            borderRadius: 10,
                            background: '#eef2f6',
                            color: '#9aa4af',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 12,
                          }}
                        >
                          无图
                        </div>
                      )}
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{item.item_id}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{item.account_id}</td>
                    <td style={{ maxWidth: 260, lineHeight: 1.5, whiteSpace: 'normal', wordBreak: 'break-word' }} title={item.title || ''}>{item.title}</td>
                    <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#666' }}>{item.description || '-'}</td>
                    <td>¥{item.price}</td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <span className={'badge ' + (item.status === 'offline' ? 'badge-warning' : item.publish_status === 'published' ? 'badge-success' : item.publish_status === 'publishing' ? 'badge-info' : item.publish_status === 'failed' ? 'badge-warning' : 'badge-secondary')}>
                          {item.status === 'offline' ? '已下架' : item.publish_status === 'published' ? '已上架' : item.publish_status === 'publishing' ? '发布中' : item.publish_status === 'failed' ? '发布失败' : '草稿'}
                        </span>
                        {item.publish_status === 'publishing' && (
                          <small style={{ fontSize: 10, color: '#856404' }}>后台处理中...</small>
                        )}
                        {item.publish_error && item.publish_status !== 'publishing' && (
                          <small style={{ fontSize: 10, color: '#c0392b', lineHeight: 1.4 }}>{item.publish_error}</small>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="table-actions">
                        <button className="neu-button" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => openEdit(item)}>编辑</button>
                        <button className="neu-button" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => openDelivery(item)}>发货配置</button>
                       <button className="neu-button" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => removeItem(item)}>删除</button>
                        {item.status === 'online' && item.publish_status !== 'publishing' && !String(item.item_id || '').startsWith('draft-') && (
                         <button className="neu-button" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => handleOffline(item)}>下架</button>
                       )}
                      {item.publish_status !== 'publishing' && (
                      <button className="neu-button" style={{ padding: '6px 12px', fontSize: 12 }} disabled={publishing} onClick={() => handlePublish(item)}>{item.publish_status === 'published' ? '重新发布' : '发布到闲鱼'}</button>
                      )}
                     </div>
                     </td>
                 </tr>
                );
              })}
              {items.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: 32, color: '#8a8a8a' }}>
                    {loading ? '加载中...' : '暂无商品，请先同步或新建草稿'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {itemModalOpen && (
        <div className="modal-overlay" onClick={closeItemModal}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 760 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
              {itemForm.item_id ? '编辑商品草稿' : '新建商品草稿'}
            </h3>
            <div style={{ display: 'grid', gap: 10 }}>
              <select className="neu-input" value={itemForm.account_id} onChange={(e) => setItemForm({ ...itemForm, account_id: e.target.value })}>
                <option value="">选择账号</option>
                {accounts.map((a: any) => (
                  <option key={a.account_id} value={a.account_id}>{a.remark || a.account_id}</option>
                ))}
              </select>
              {itemForm.item_id && (
                <input className="neu-input" value={itemForm.item_id} disabled placeholder="商品ID" />
              )}
              <input className="neu-input" maxLength={30} value={itemForm.title} onChange={(e) => setItemForm({ ...itemForm, title: e.target.value })} placeholder="标题（最多 30 字）" />
              <div style={{ fontSize: 12, color: '#8a8a8a', marginTop: -4 }}>闲鱼标题最多 30 字，当前 {itemForm.title.length}/30</div>
              <input className="neu-input" type="number" min="0" step="0.01" value={itemForm.price} onChange={(e) => setItemForm({ ...itemForm, price: e.target.value })} placeholder="价格" />
              <input className="neu-input" value={itemForm.url} onChange={(e) => setItemForm({ ...itemForm, url: e.target.value })} placeholder="链接" />
              <textarea className="neu-input" value={itemForm.description} onChange={(e) => setItemForm({ ...itemForm, description: e.target.value })} placeholder="描述" />

              <div className="neu-card-sm" style={{ padding: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#2d5a8a', marginBottom: 8 }}>商品图片</div>
                <div style={{ fontSize: 12, color: '#8a8a8a', marginBottom: 12 }}>
                  支持上传 jpg / jpeg / png / webp / gif，单张不超过 10MB。
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
                  <label className="neu-button" style={{ cursor: 'pointer' }}>
                    {uploading ? '上传中...' : '上传图片'}
                    <input type="file" accept="image/*" multiple style={{ display: 'none' }} onChange={handleUploadImage} disabled={uploading || imageList.length >= MAX_ITEM_IMAGES} />
                  </label>
                  <span style={{ fontSize: 12, color: '#8a8a8a' }}>当前 {imageList.length}/{MAX_ITEM_IMAGES} 张</span>
                </div>
                {imageList.length > 0 ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: 10 }}>
                    {imageList.map((url: string) => (
                      <div key={url} className="neu-card-sm" style={{ padding: 8 }}>
                        <img
                          src={url}
                          alt="商品图片"
                          style={{ width: '100%', height: 90, objectFit: 'cover', borderRadius: 10, marginBottom: 8 }}
                        />
                        <button
                          className="neu-button"
                          style={{ width: '100%', fontSize: 12, padding: '6px 10px', color: '#c0392b' }}
                          onClick={() => handleRemoveImage(url)}
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: '#8a8a8a' }}>暂无图片</div>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <button className="neu-button" onClick={closeItemModal}>取消</button>
              <button className="neu-button neu-button-primary" onClick={saveItem}>保存</button>
            </div>
          </div>
        </div>
      )}

      {editing && (
        <div className="modal-overlay" onClick={() => setEditing(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 620 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>商品发货配置</h3>
            <p style={{ fontSize: 13, color: '#666', marginBottom: 12 }}>{editing.title || editing.item_id}</p>
            <p style={{ fontSize: 12, color: '#8a8a8a', lineHeight: 1.7, marginBottom: 12 }}>
              这里填写买家付款后系统自动发给对方的内容，例如卡密、网盘链接、提取码、使用说明等。
            </p>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 12 }}>
              <input type="checkbox" checked={deliveryEnabled} onChange={(e) => setDeliveryEnabled(e.target.checked)} /> 启用自动发货
            </label>
            <textarea
              className="neu-input"
              style={{ minHeight: 160, resize: 'vertical' }}
              value={deliveryContent}
              onChange={(e) => setDeliveryContent(e.target.value)}
              placeholder="买家付款后自动发送的内容，例如卡密、网盘链接、使用说明等。"
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <button className="neu-button" onClick={() => setEditing(null)}>取消</button>
              <button className="neu-button neu-button-primary" onClick={saveDelivery}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
