import React, { useState } from 'react';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        localStorage.setItem('token', data.token);
        window.location.href = '/dashboard';
      } else {
        setError(data.detail || '登录失败');
      }
    } catch {
      setError('网络错误，请检查服务是否启动');
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#e8e8e8' }}>
      <div className="neu-card" style={{ width: 380, padding: 40 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>🐟</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#2d5a8a' }}>闲鱼助手 Lite</h1>
          <p style={{ fontSize: 13, color: '#8a8a8a', marginTop: 4 }}>多账号自动回复管理系统</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, color: '#6a6a6a', marginBottom: 6, display: 'block' }}>用户名</label>
            <input className="neu-input" value={username} onChange={e => setUsername(e.target.value)} placeholder="输入用户名" />
          </div>
          <div style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 13, color: '#6a6a6a', marginBottom: 6, display: 'block' }}>密码</label>
            <input className="neu-input" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="输入密码" />
          </div>
          {error && <p style={{ color: '#c0392b', fontSize: 13, marginBottom: 12, textAlign: 'center' }}>{error}</p>}
          <button type="submit" className="neu-button neu-button-primary" style={{ width: '100%', padding: 12, fontSize: 15 }}>登录</button>
        </form>
      </div>
    </div>
  );
}
