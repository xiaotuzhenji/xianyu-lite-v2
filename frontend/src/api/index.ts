// @ts-nocheck
const API_BASE = import.meta.env.VITE_API_URL || '';

const parseResponse = async (res: Response) => {
  const text = await res.text();
  if (!text) {
    return { success: res.ok };
  }
  try {
    return JSON.parse(text);
  } catch {
    const message = text.startsWith('<') ? '服务返回了非 JSON 内容，请检查后端服务或反向代理' : text.slice(0, 200);
    return { success: false, error: message, detail: message, status: res.status };
  }
};

export const login = async (username: string, password: string) => {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  return parseResponse(res);
};

export const getAccounts = async (page = 1, pageSize = 20) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/accounts?page=${page}&page_size=${pageSize}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const updateAccount = async (accountId: string, data: any) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/accounts/${accountId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return parseResponse(res);
};

export const deleteAccount = async (accountId: string) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/accounts/${accountId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const getItems = async (accountId?: string) => {
  const token = localStorage.getItem('token');
  const params = accountId ? `?account_id=${accountId}` : '?page_size=100';
  const res = await fetch(`${API_BASE}/api/v1/items${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const createItem = async (data: any) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return parseResponse(res);
};

export const updateItem = async (itemId: string, data: any) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/items/${itemId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return parseResponse(res);
};

export const deleteItem = async (itemId: string) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/items/${itemId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const uploadItemImage = async (file: File) => {
  const token = localStorage.getItem('token');
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/api/v1/items/upload-image`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  return parseResponse(res);
};

export const getKeywords = async (accountId?: string) => {
  const token = localStorage.getItem('token');
  const params = accountId ? `?account_id=${accountId}` : '';
  const res = await fetch(`${API_BASE}/api/v1/keywords${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const createKeyword = async (data: any) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/keywords`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return parseResponse(res);
};

export const deleteKeyword = async (id: number) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/keywords/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const getConfirmReceiptConfig = async (accountId: string, itemId?: string) => {
  const token = localStorage.getItem('token');
  const params = itemId ? `?item_id=${itemId}` : '';
  const res = await fetch(`${API_BASE}/api/v1/confirm-receipt/${accountId}${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const updateConfirmReceiptConfig = async (accountId: string, data: any) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/confirm-receipt/${accountId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return parseResponse(res);
};

export const getOrders = async (accountId?: string, page = 1) => {
  const token = localStorage.getItem('token');
  const params = accountId ? `?account_id=${accountId}&page=${page}` : `?page=${page}`;
  const res = await fetch(`${API_BASE}/api/v1/orders${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const getOverview = async () => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/statistics/overview`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const getDailyStats = async (days = 7) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/statistics/daily?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const createAccount = async (data: any) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return parseResponse(res);
};



export const generateQR = async () => {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/v1/qr-login/generate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const getQRStatus = async (sessionId: string) => {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/v1/qr-login/status/${sessionId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const startQRPoll = async (sessionId: string) => {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/v1/qr-login/poll/${sessionId}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};


export const syncItems = async (accountId?: string) => {
  const token = localStorage.getItem("token");
  const params = accountId ? `?account_id=${accountId}` : "";
  const res = await fetch(`${API_BASE}/api/v1/items/sync${params}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const syncOrders = async (accountId?: string, queryCode = "NOT_SHIP") => {
  const token = localStorage.getItem("token");
  const params = new URLSearchParams({ query_code: queryCode, max_pages: "3" });
  if (accountId) params.set("account_id", accountId);
  const res = await fetch(`${API_BASE}/api/v1/orders/sync?${params.toString()}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const getDeliveryConfig = async (accountId: string, itemId: string) => {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/v1/delivery/configs/${accountId}/${itemId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const saveDeliveryConfig = async (accountId: string, data: any) => {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/v1/delivery/configs/${accountId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return parseResponse(res);
};

export const getDeliveryLogs = async (accountId?: string, itemId?: string, page = 1) => {
  const token = localStorage.getItem("token");
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (accountId) params.set("account_id", accountId);
  if (itemId) params.set("item_id", itemId);
  const res = await fetch(`${API_BASE}/api/v1/delivery/logs?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const deliverOrder = async (orderId: string) => {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/v1/delivery/orders/${orderId}/deliver`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const getProductionDiagnostics = async () => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/diagnostics/production`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseResponse(res);
};

export const publishItem = async (itemId: string) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/publish/item`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ item_id: itemId }),
  });
  return parseResponse(res);
};

export const offlineItem = async (itemId: string) => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_BASE}/api/v1/publish/item/offline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ item_id: itemId }),
  });
  return parseResponse(res);
};
